import { ethers } from "ethers";

/**
 * Backend oracle signer.
 *
 * SECURITY: This module reads ORACLE_PRIVATE_KEY from env and NEVER exposes it
 * to the frontend. The derived address must match the contract's oracleSigner.
 *
 * Signed payloads use EIP-191 (personal_sign-compatible) hashing, matching
 * the contract's _openMsgHash / _closeMsgHash.
 */

function getOracleWallet(): ethers.Wallet {
  const pk = process.env.ORACLE_PRIVATE_KEY;
  if (!pk || !pk.startsWith("0x") || pk.length !== 66) {
    throw new Error("ORACLE_PRIVATE_KEY missing or malformed");
  }
  return new ethers.Wallet(pk);
}

export function oracleSignerAddress(): string {
  return getOracleWallet().address;
}

function ethSignedHash(structHash: string): string {
  return ethers.keccak256(
    ethers.solidityPacked(
      ["string", "bytes32"],
      ["\x19Ethereum Signed Message:\n32", ethers.getBytes(structHash)]
    )
  );
}

export interface OpenSigInput {
  pairId: string;        // bytes32 hex
  priceScaled: bigint;   // price * 1e8
  timestamp: number;
  trader: string;
  chainId: number;
  contractAddress: string;
}

export function signOpenPrice(i: OpenSigInput): string {
  const w = getOracleWallet();
  const structHash = ethers.keccak256(
    ethers.AbiCoder.defaultAbiCoder().encode(
      ["bytes32", "uint256", "uint256", "address", "uint256", "address"],
      [i.pairId, i.priceScaled, i.timestamp, i.trader, i.chainId, i.contractAddress]
    )
  );
  const msgHash = ethSignedHash(structHash);
  return w.signingKey.sign(msgHash).serialized;
}

export interface CloseSigInput {
  tradeId: number;
  priceScaled: bigint;
  timestamp: number;
  nonce: string;        // bytes32 hex
  chainId: number;
  contractAddress: string;
}

export function signClosePrice(i: CloseSigInput): string {
  const w = getOracleWallet();
  const structHash = ethers.keccak256(
    ethers.AbiCoder.defaultAbiCoder().encode(
      ["uint256", "uint256", "uint256", "bytes32", "uint256", "address"],
      [BigInt(i.tradeId), i.priceScaled, i.timestamp, i.nonce, i.chainId, i.contractAddress]
    )
  );
  const msgHash = ethSignedHash(structHash);
  return w.signingKey.sign(msgHash).serialized;
}

export function newNonce(): string {
  return ethers.hexlify(ethers.randomBytes(32));
}
