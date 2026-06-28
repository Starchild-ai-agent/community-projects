// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title TradingGame
 * @notice On-chain settlement layer for a leveraged up/down trading game.
 *
 * @dev SECURITY MODEL
 *   - Margin is real ERC20 (USDT or platform token). No fake balances.
 *   - The contract NEVER trusts a price submitted by the user's frontend.
 *   - Close price is signed off-chain by a backend ORACLE SIGNER.
 *   - The contract verifies the signature with ecrecover before settling.
 *   - Each close payload carries a nonce; used nonces are burned (replay-proof).
 *   - Margin is LOCKED when a trade opens and only released on close.
 *   - PnL is capped: profit <= maxProfitPct of margin, loss >= -maxLossPct.
 *   - One active trade per user by default (admin can toggle).
 *
 *   FORMULA (matches frontend/backend exactly):
 *     priceMovePct = ((close - open) / open) * 100            [UP]
 *     priceMovePct = ((open - close) / open) * 100            [DOWN]
 *     leveragedROI = priceMovePct * leverage                  // percent
 *     pnl = margin * leveragedROI / 100
 */

import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";

contract TradingGame is ReentrancyGuard, Ownable, Pausable {
    using SafeERC20 for IERC20;

    uint256 public constant HARD_MAX_PROFIT_PCT = 100; // +100% ROI hard ceiling (admin can lower, never raise above)
    uint256 public constant HARD_MAX_LOSS_PCT = 50;    // -50% of margin hard ceiling
    uint256 public constant HARD_MAX_LEVERAGE = 1000;
    uint256 public constant DEFAULT_TP_SL_PCT = 40;    // default TP/SL cap = 40% of margin

    enum Direction { UP, DOWN }

    struct Trade {
        address trader;
        bytes32 pairId;
        Direction direction;
        uint256 margin;
        uint256 leverage;
        uint256 openPrice;   // price * 1e8
        uint256 tpPct;       // take-profit % of margin (0 = none)
        uint256 slPct;       // stop-loss % of margin (0 = none)
        uint256 openTimestamp;
        bool closed;
        uint256 closePrice;
        uint256 closeTimestamp;
        int256 pnl;          // realized pnl (signed, base units)
    }

    IERC20 public marginToken;
    address public oracleSigner;

    uint256 public maxProfitPct = DEFAULT_TP_SL_PCT;   // default +40% (admin can raise up to HARD_MAX)
    uint256 public maxLossPct = DEFAULT_TP_SL_PCT;     // default -40% (admin can raise up to HARD_MAX)
    uint256 public platformFeePct = 0;
    address public feeRecipient;
    bool public oneTradePerUser = true;

    mapping(uint256 => Trade) public trades;
    mapping(address => uint256[]) public userTradeIds;
    mapping(address => uint256) public userOpenCount;
    mapping(bytes32 => bool) public supportedPairs;
    mapping(bytes32 => uint256) public pairMaxLeverage;
    mapping(bytes32 => bool) public usedNonces;
    mapping(address => uint256) public deposited;

    uint256 public nextTradeId = 1;

    event TradeOpened(
        uint256 indexed tradeId, address indexed trader, bytes32 pairId,
        Direction direction, uint256 margin, uint256 leverage,
        uint256 openPrice, uint256 tpPct, uint256 slPct, uint256 openTimestamp
    );
    event TradeClosed(
        uint256 indexed tradeId, address indexed trader,
        uint256 closePrice, uint256 closeTimestamp, int256 pnl, uint256 fee, bytes32 nonce
    );
    event Deposit(address indexed user, uint256 amount);
    event Withdraw(address indexed user, uint256 amount);
    event OracleSignerUpdated(address oldSigner, address newSigner);
    event PairUpdated(bytes32 indexed pairId, bool supported, uint256 maxLeverage);
    event RiskParamsUpdated(uint256 maxProfitPct, uint256 maxLossPct, uint256 platformFeePct);
    event NonceBurned(bytes32 indexed nonce);

    constructor(address _marginToken, address _oracleSigner, address _feeRecipient) Ownable(msg.sender) {
        require(_marginToken != address(0), "bad token");
        require(_oracleSigner != address(0), "bad oracle");
        marginToken = IERC20(_marginToken);
        oracleSigner = _oracleSigner;
        feeRecipient = _feeRecipient;
    }

    modifier onlySupportedPair(bytes32 pairId) {
        require(supportedPairs[pairId], "pair not supported");
        _;
    }

    // ----- ERC20 float -----

    function deposit(uint256 amount) external nonReentrant whenNotPaused {
        require(amount > 0, "zero amount");
        deposited[msg.sender] += amount;
        marginToken.safeTransferFrom(msg.sender, address(this), amount);
        emit Deposit(msg.sender, amount);
    }

    function withdraw(uint256 amount) external nonReentrant {
        require(amount > 0, "zero amount");
        require(deposited[msg.sender] >= amount, "insufficient balance");
        deposited[msg.sender] -= amount;
        marginToken.safeTransfer(msg.sender, amount);
        emit Withdraw(msg.sender, amount);
    }

    // ----- Trade lifecycle -----

    function openTrade(
        bytes32 pairId,
        Direction direction,
        uint256 margin,
        uint256 leverage,
        uint256 tpPct,
        uint256 slPct,
        uint256 openPrice,
        uint256 openTimestamp,
        bytes calldata oracleSig
    ) external nonReentrant whenNotPaused onlySupportedPair(pairId) {
        require(margin > 0, "zero margin");
        require(leverage > 0 && leverage <= HARD_MAX_LEVERAGE, "bad leverage");
        require(tpPct <= maxProfitPct, "tp too high");
        require(slPct <= maxLossPct, "sl too high");
        require(tpPct <= 40, "tp > 40%");              // TP capped at 40% of margin
        require(slPct <= 40, "sl > 40%");              // SL capped at 40% of margin
        require(deposited[msg.sender] >= margin, "insufficient deposited");
        require(openPrice > 0, "bad open price");
        require(block.timestamp >= openTimestamp && block.timestamp - openTimestamp <= 60, "stale open price");

        uint256 pairLevCap = pairMaxLeverage[pairId];
        if (pairLevCap > 0) require(leverage <= pairLevCap, "lev > pair cap");

        if (oneTradePerUser) require(userOpenCount[msg.sender] == 0, "one open trade max");

        bytes32 msgHash = _openMsgHash(pairId, openPrice, openTimestamp, msg.sender);
        require(_verifySig(msgHash, oracleSig, oracleSigner), "bad open sig");

        deposited[msg.sender] -= margin;
        uint256 tradeId = nextTradeId++;
        trades[tradeId] = Trade({
            trader: msg.sender, pairId: pairId, direction: direction,
            margin: margin, leverage: leverage, openPrice: openPrice,
            tpPct: tpPct, slPct: slPct, openTimestamp: openTimestamp,
            closed: false, closePrice: 0, closeTimestamp: 0, pnl: 0
        });
        userTradeIds[msg.sender].push(tradeId);
        userOpenCount[msg.sender] += 1;

        emit TradeOpened(tradeId, msg.sender, pairId, direction, margin, leverage, openPrice, tpPct, slPct, openTimestamp);
    }

    function closeTrade(
        uint256 tradeId,
        uint256 closePrice,
        uint256 closeTimestamp,
        bytes32 nonce,
        bytes calldata oracleSig
    ) external nonReentrant whenNotPaused {
        Trade storage t = trades[tradeId];
        require(t.trader != address(0), "no such trade");
        require(!t.closed, "already closed");
        require(t.trader == msg.sender, "not owner");
        require(closePrice > 0, "bad close price");
        require(block.timestamp >= closeTimestamp && block.timestamp - closeTimestamp <= 60, "stale close price");
        require(!usedNonces[nonce], "nonce used");

        bytes32 msgHash = _closeMsgHash(tradeId, closePrice, closeTimestamp, nonce);
        require(_verifySig(msgHash, oracleSig, oracleSigner), "bad close sig");

        usedNonces[nonce] = true;
        emit NonceBurned(nonce);

        (int256 pnl, uint256 fee) = _settle(t, closePrice);

        t.closed = true;
        t.closePrice = closePrice;
        t.closeTimestamp = closeTimestamp;
        t.pnl = pnl;
        userOpenCount[msg.sender] -= 1;

        int256 credit = int256(t.margin) + pnl - int256(fee);
        if (credit < 0) credit = 0;
        deposited[msg.sender] += uint256(credit);
        if (fee > 0 && feeRecipient != address(0)) {
            marginToken.safeTransfer(feeRecipient, fee);
        }

        emit TradeClosed(tradeId, msg.sender, closePrice, closeTimestamp, pnl, fee, nonce);
    }

    /**
     * @notice Auto-close a trade when TP/SL is breached. Anyone may call this
     *         (no msg.sender == trader check) because the oracle signature
     *         guarantees the close price is authentic and the settlement caps
     *         PnL at the trade's TP/SL levels. A relayer bot uses this to
     *         auto-close positions without the trader being online.
     */
    function autoCloseTrade(
        uint256 tradeId,
        uint256 closePrice,
        uint256 closeTimestamp,
        bytes32 nonce,
        bytes calldata oracleSig
    ) external nonReentrant whenNotPaused {
        Trade storage t = trades[tradeId];
        require(t.trader != address(0), "no such trade");
        require(!t.closed, "already closed");
        require(closePrice > 0, "bad close price");
        require(block.timestamp >= closeTimestamp && block.timestamp - closeTimestamp <= 60, "stale close price");
        require(!usedNonces[nonce], "nonce used");

        bytes32 msgHash = _closeMsgHash(tradeId, closePrice, closeTimestamp, nonce);
        require(_verifySig(msgHash, oracleSig, oracleSigner), "bad close sig");

        usedNonces[nonce] = true;
        emit NonceBurned(nonce);

        (int256 pnl, uint256 fee) = _settle(t, closePrice);

        t.closed = true;
        t.closePrice = closePrice;
        t.closeTimestamp = closeTimestamp;
        t.pnl = pnl;
        userOpenCount[t.trader] -= 1;

        int256 credit = int256(t.margin) + pnl - int256(fee);
        if (credit < 0) credit = 0;
        deposited[t.trader] += uint256(credit);
        if (fee > 0 && feeRecipient != address(0)) {
            marginToken.safeTransfer(feeRecipient, fee);
        }

        emit TradeClosed(tradeId, t.trader, closePrice, closeTimestamp, pnl, fee, nonce);
    }

    // ----- Settlement math (pure, matches off-chain formula) -----

    function _settle(Trade storage t, uint256 closePrice) internal view returns (int256 pnl, uint256 fee) {
        int256 delta;
        if (t.direction == Direction.UP) {
            delta = int256(closePrice) - int256(t.openPrice);
        } else {
            delta = int256(t.openPrice) - int256(closePrice);
        }
        // pnl = margin * delta * leverage / openPrice / 1e8
        int256 rawPnl = (int256(t.margin) * delta * int256(t.leverage)) / int256(t.openPrice) / 1e8;

        int256 maxProfit = int256((t.margin * maxProfitPct) / 100);
        int256 maxLoss = -int256((t.margin * maxLossPct) / 100);
        if (rawPnl > maxProfit) rawPnl = maxProfit;
        if (rawPnl < maxLoss) rawPnl = maxLoss;

        if (t.tpPct > 0 && rawPnl >= int256((t.margin * t.tpPct) / 100)) {
            rawPnl = int256((t.margin * t.tpPct) / 100);
        }
        if (t.slPct > 0 && rawPnl <= -int256((t.margin * t.slPct) / 100)) {
            rawPnl = -int256((t.margin * t.slPct) / 100);
        }

        fee = (t.margin * platformFeePct) / 100;
        pnl = rawPnl;
    }

    // ----- Signature helpers (EIP-191) -----

    function _openMsgHash(bytes32 pairId, uint256 price, uint256 ts, address trader) internal view returns (bytes32) {
        bytes32 h = keccak256(abi.encode(pairId, price, ts, trader, block.chainid, address(this)));
        return keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", h));
    }

    function _closeMsgHash(uint256 tradeId, uint256 price, uint256 ts, bytes32 nonce) internal view returns (bytes32) {
        bytes32 h = keccak256(abi.encode(tradeId, price, ts, nonce, block.chainid, address(this)));
        return keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", h));
    }

    function _verifySig(bytes32 msgHash, bytes calldata sig, address expected) internal pure returns (bool) {
        if (sig.length != 65) return false;
        bytes32 r; bytes32 s; uint8 v;
        assembly {
            r := calldataload(sig.offset)
            s := calldataload(add(sig.offset, 32))
            v := byte(0, calldataload(add(sig.offset, 64)))
        }
        if (v < 27) v += 27;
        address recovered = ecrecover(msgHash, v, r, s);
        return recovered != address(0) && recovered == expected;
    }

    // ----- Admin -----

    function adminSetOracleSigner(address signer) external onlyOwner {
        require(signer != address(0), "bad signer");
        emit OracleSignerUpdated(oracleSigner, signer);
        oracleSigner = signer;
    }

    function adminSetSupportedToken(address token) external onlyOwner {
        require(token != address(0), "bad token");
        marginToken = IERC20(token);
    }

    function adminSetPair(bytes32 pairId, bool supported, uint256 maxLeverage) external onlyOwner {
        supportedPairs[pairId] = supported;
        pairMaxLeverage[pairId] = maxLeverage;
        emit PairUpdated(pairId, supported, maxLeverage);
    }

    function adminSetRiskParams(uint256 _maxProfitPct, uint256 _maxLossPct, uint256 _feePct) external onlyOwner {
        require(_maxProfitPct <= HARD_MAX_PROFIT_PCT, "profit cap too high");
        require(_maxLossPct >= 1 && _maxLossPct <= HARD_MAX_LOSS_PCT, "loss cap out of range");
        require(_feePct <= 50, "fee too high");
        maxProfitPct = _maxProfitPct;
        maxLossPct = _maxLossPct;
        platformFeePct = _feePct;
        emit RiskParamsUpdated(_maxProfitPct, _maxLossPct, _feePct);
    }

    function adminSetFeeRecipient(address r) external onlyOwner {
        require(r != address(0), "bad recipient");
        feeRecipient = r;
    }

    function adminSetOneTradePerUser(bool v) external onlyOwner { oneTradePerUser = v; }
    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }

    // ----- Views -----

    function getTrade(uint256 tradeId) external view returns (Trade memory) { return trades[tradeId]; }
    function getUserTrades(address user) external view returns (uint256[] memory) { return userTradeIds[user]; }
    function pairIdFromString(string calldata s) external pure returns (bytes32) {
        return keccak256(abi.encodePacked(s));
    }
}
