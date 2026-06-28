// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../contracts/TradingGame.sol";
import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

contract MockUSDT is ERC20 {
    constructor() ERC20("Mock USDT", "USDT") {
        _mint(msg.sender, 1_000_000 * 1e18);
    }
}

contract TradingGameTest is Test {
    TradingGame public game;
    MockUSDT public usdt;
    uint256 public oraclePk;
    address public oracleSigner;
    address user = address(0xA11CE);
    address feeRec = address(0xFEE);

    function setUp() public {
        usdt = new MockUSDT();
        (oracleSigner, oraclePk) = makeAddrAndKey("oracle");
        game = new TradingGame(address(usdt), oracleSigner, feeRec);
        bytes32 sol = keccak256("SOL-PERP");
        game.adminSetPair(sol, true, 1000);

        usdt.transfer(user, 10_000 * 1e18);
        vm.startPrank(user);
        usdt.approve(address(game), type(uint256).max);
        game.deposit(100 * 1e18);
        vm.stopPrank();
    }

    function _signOpen(bytes32 pairId, uint256 price, uint256 ts, address trader) internal returns (bytes memory) {
        bytes32 h = keccak256(abi.encode(pairId, price, ts, trader, block.chainid, address(game)));
        bytes32 mh = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", h));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(oraclePk, mh);
        return abi.encodePacked(r, s, v);
    }

    function _signClose(uint256 tradeId, uint256 price, uint256 ts, bytes32 nonce) internal returns (bytes memory) {
        bytes32 h = keccak256(abi.encode(tradeId, price, ts, nonce, block.chainid, address(game)));
        bytes32 mh = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", h));
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(oraclePk, mh);
        return abi.encodePacked(r, s, v);
    }

    function testOpenAndCloseDown() public {
        bytes32 sol = keccak256("SOL-PERP");
        uint256 openPrice = 72_7349 * 1e4;   // 72.7349 * 1e8
        uint256 closePrice = 72_7193 * 1e4;  // 72.7193 * 1e8
        uint256 margin = 5 * 1e18;
        uint256 lev = 1000;

        vm.warp(block.timestamp + 1);
        bytes memory openSig = _signOpen(sol, openPrice, block.timestamp, user);

        vm.startPrank(user);
        game.openTrade(sol, TradingGame.Direction.DOWN, margin, lev, 0, 0, openPrice, block.timestamp, openSig);

        vm.warp(block.timestamp + 30);
        bytes32 nonce = keccak256("nonce-1");
        bytes memory closeSig = _signClose(1, closePrice, block.timestamp, nonce);
        game.closeTrade(1, closePrice, block.timestamp, nonce, closeSig);
        vm.stopPrank();

        TradingGame.Trade memory t = game.getTrade(1);
        assertTrue(t.closed);
        int256 expected = int256(margin) * int256(int256(openPrice) - int256(closePrice)) * int256(lev) / int256(openPrice) / 1e8;
        assertEq(t.pnl, expected);
    }

    function testReplayNonceRejected() public {
        bytes32 sol = keccak256("SOL-PERP");
        uint256 openPrice = 100 * 1e8;
        uint256 margin = 5 * 1e18;

        vm.warp(block.timestamp + 1);
        bytes memory openSig = _signOpen(sol, openPrice, block.timestamp, user);
        vm.startPrank(user);
        game.openTrade(sol, TradingGame.Direction.UP, margin, 1000, 0, 0, openPrice, block.timestamp, openSig);

        bytes32 nonce = keccak256("nonce-x");
        bytes memory closeSig = _signClose(1, 101 * 1e8, block.timestamp, nonce);
        game.closeTrade(1, 101 * 1e8, block.timestamp, nonce, closeSig);

        bytes memory closeSig2 = _signClose(1, 102 * 1e8, block.timestamp, nonce);
        vm.expectRevert("nonce used");
        game.closeTrade(1, 102 * 1e8, block.timestamp, nonce, closeSig2);
        vm.stopPrank();
    }

    function testProfitCapped() public {
        bytes32 sol = keccak256("SOL-PERP");
        uint256 openPrice = 100 * 1e8;
        uint256 margin = 5 * 1e18;

        vm.warp(block.timestamp + 1);
        bytes memory openSig = _signOpen(sol, openPrice, block.timestamp, user);
        vm.startPrank(user);
        // TP=40 → profit capped at 40% of margin
        game.openTrade(sol, TradingGame.Direction.UP, margin, 1000, 40, 0, openPrice, block.timestamp, openSig);

        bytes32 nonce = keccak256("n1");
        bytes memory closeSig = _signClose(1, 1000 * 1e8, block.timestamp, nonce);
        game.closeTrade(1, 1000 * 1e8, block.timestamp, nonce, closeSig);

        TradingGame.Trade memory t = game.getTrade(1);
        assertEq(t.pnl, int256(margin * 40 / 100));
        vm.stopPrank();
    }

    function testLossCapped() public {
        bytes32 sol = keccak256("SOL-PERP");
        uint256 openPrice = 100 * 1e8;
        uint256 margin = 5 * 1e18;

        vm.warp(block.timestamp + 1);
        bytes memory openSig = _signOpen(sol, openPrice, block.timestamp, user);
        vm.startPrank(user);
        // SL=40 → loss capped at 40% of margin
        game.openTrade(sol, TradingGame.Direction.UP, margin, 1000, 0, 40, openPrice, block.timestamp, openSig);

        bytes32 nonce = keccak256("n2");
        bytes memory closeSig = _signClose(1, 1 * 1e8, block.timestamp, nonce);
        game.closeTrade(1, 1 * 1e8, block.timestamp, nonce, closeSig);

        TradingGame.Trade memory t = game.getTrade(1);
        assertEq(t.pnl, -int256(margin * 40 / 100));
        vm.stopPrank();
    }

    function testTpSlCappedAt40() public {
        bytes32 sol = keccak256("SOL-PERP");
        uint256 openPrice = 100 * 1e8;
        uint256 margin = 5 * 1e18;

        vm.warp(block.timestamp + 1);
        bytes memory openSig = _signOpen(sol, openPrice, block.timestamp, user);
        vm.startPrank(user);
        vm.expectRevert("tp > 40%");
        game.openTrade(sol, TradingGame.Direction.UP, margin, 1000, 50, 0, openPrice, block.timestamp, openSig);
        vm.expectRevert("sl > 40%");
        game.openTrade(sol, TradingGame.Direction.UP, margin, 1000, 0, 50, openPrice, block.timestamp, openSig);
        vm.stopPrank();
    }

    function testAutoCloseByRelayer() public {
        bytes32 sol = keccak256("SOL-PERP");
        uint256 openPrice = 100 * 1e8;
        uint256 margin = 5 * 1e18;

        vm.warp(block.timestamp + 1);
        bytes memory openSig = _signOpen(sol, openPrice, block.timestamp, user);
        vm.prank(user);
        game.openTrade(sol, TradingGame.Direction.UP, margin, 1000, 40, 40, openPrice, block.timestamp, openSig);

        // Relayer (not the trader) auto-closes
        address relayer = address(0xB0B);
        vm.warp(block.timestamp + 30);
        bytes32 nonce = keccak256("auto-1");
        bytes memory closeSig = _signClose(1, 50 * 1e8, block.timestamp, nonce);
        vm.prank(relayer);
        game.autoCloseTrade(1, 50 * 1e8, block.timestamp, nonce, closeSig);

        TradingGame.Trade memory t = game.getTrade(1);
        assertTrue(t.closed);
        assertEq(t.pnl, -int256(margin * 40 / 100)); // SL=40 caps the loss
    }

    function testOneTradePerUser() public {
        bytes32 sol = keccak256("SOL-PERP");
        uint256 openPrice = 100 * 1e8;
        uint256 margin = 5 * 1e18;

        vm.warp(block.timestamp + 1);
        bytes memory openSig = _signOpen(sol, openPrice, block.timestamp, user);
        vm.startPrank(user);
        game.openTrade(sol, TradingGame.Direction.UP, margin, 1000, 0, 0, openPrice, block.timestamp, openSig);

        vm.warp(block.timestamp + 1);
        bytes memory openSig2 = _signOpen(sol, openPrice, block.timestamp, user);
        vm.expectRevert("one open trade max");
        game.openTrade(sol, TradingGame.Direction.UP, margin, 1000, 0, 0, openPrice, block.timestamp, openSig2);
        vm.stopPrank();
    }
}
