import { ethers } from "hardhat";

async function main() {
  const w = ethers.Wallet.createRandom();
  console.log("=== Oracle Signer (DEV ONLY) ===");
  console.log("Address:    ", w.address);
  console.log("Private key:", w.privateKey);
  console.log("");
  console.log("Add to web/.env.local:");
  console.log(`ORACLE_SIGNER_ADDRESS=${w.address}`);
  console.log(`ORACLE_PRIVATE_KEY=${w.privateKey}`);
}

main().catch((e) => { console.error(e); process.exit(1); });
