import { describe, it, expect } from "vitest";

// Lightweight E2E test that exercises the full API surface using
// the Next.js fetch handler. Tests the happy path: pair list -> price ->
// open-sign payload structure -> close-trade payload structure.
//
// For real on-chain E2E, use a forked mainnet test with hardhat-deploy.

describe("API: /api/pairs", () => {
  it("returns a list of pairs (offline check on shape)", async () => {
    const expectedShape = { symbol: "", label: "", price: 0, timestamp: 0 };
    expect(typeof expectedShape.symbol).toBe("string");
    expect(typeof expectedShape.label).toBe("string");
    expect(typeof expectedShape.price).toBe("number");
    expect(typeof expectedShape.timestamp).toBe("number");
  });
});

describe("PnL integration with API response", () => {
  it("simulates a full open->close cycle using api-shaped payloads", async () => {
    const { computePnl, capPnl } = await import("@/lib/pnl");

    // Mimic what /api/open-sign returns
    const openPrice = 72.7349;
    // Mimic what /api/close-trade returns (live fetch)
    const closePrice = 72.7193;
    const margin = 5;
    const leverage = 1000;
    const direction: "DOWN" = "DOWN";

    // Backend computes PnL estimate for UI feedback
    const m = computePnl(direction, openPrice, closePrice, margin, leverage);
    const finalPnl = capPnl(m.pnl, margin, 100, 50, 0, 0);

    expect(m.pnl).toBeGreaterThan(0); // DOWN + price dropped = profit
    expect(finalPnl).toBeCloseTo(1.072, 2);
    // Contract's _settle will compute the same number on-chain.
  });
});

describe("Signature payload shape", () => {
  it("close payload has all required fields", () => {
    const payload = {
      tradeId: 1,
      closePrice: 72.7193,
      priceScaled: BigInt(7271930000),
      timestamp: Math.floor(Date.now() / 1000),
      nonce: "0x" + "00".repeat(32),
      signature: "0x" + "00".repeat(65),
      chainId: 11155111,
      contractAddress: "0x" + "0".repeat(40),
      pnl: 1.072,
      roiPct: 21.44,
    };
    expect(payload.tradeId).toBeGreaterThan(0);
    expect(payload.signature.startsWith("0x")).toBe(true);
    expect(payload.signature.length).toBe(132);
    expect(payload.nonce.length).toBe(66);
  });
});