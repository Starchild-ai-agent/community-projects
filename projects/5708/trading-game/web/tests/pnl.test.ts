import { describe, it, expect } from "vitest";
import { computePnl, capPnl } from "@/lib/pnl";

describe("pnl formula", () => {
  it("matches the reference example", () => {
    // margin 5, lev 1000, open 72.7349, close 72.7193, DOWN
    const m = computePnl("DOWN", 72.7349, 72.7193, 5, 1000);
    expect(m.priceMovePct).toBeCloseTo(0.02144, 4);
    expect(m.roiPct).toBeCloseTo(21.44, 1);
    expect(m.pnl).toBeCloseTo(1.072, 2);
  });

  it("UP: positive move -> positive pnl", () => {
    const m = computePnl("UP", 100, 101, 10, 100);
    expect(m.priceMovePct).toBeCloseTo(1, 5);
    expect(m.roiPct).toBeCloseTo(100, 5);
    expect(m.pnl).toBeCloseTo(10, 5);
  });

  it("DOWN: positive move -> negative pnl", () => {
    const m = computePnl("DOWN", 100, 101, 10, 100);
    expect(m.priceMovePct).toBeCloseTo(-1, 5);
    expect(m.pnl).toBeCloseTo(-10, 5);
  });

  it("flat price -> zero pnl", () => {
    const m = computePnl("UP", 50, 50, 5, 1000);
    expect(m.pnl).toBe(0);
  });
});

describe("capPnl", () => {
  it("caps profit at +100% of margin", () => {
    const p = capPnl(100, 5, 100, 50, 0, 0);
    expect(p).toBe(5);
  });
  it("caps loss at -50% of margin", () => {
    const p = capPnl(-100, 10, 100, 50, 0, 0);
    expect(p).toBe(-5);
  });
  it("triggers TP at tp_pct", () => {
    const p = capPnl(0.4, 5, 100, 50, 5, 0);
    expect(p).toBe(0.25);
  });
  it("triggers SL at sl_pct", () => {
    const p = capPnl(-0.4, 5, 100, 50, 0, 5);
    expect(p).toBe(-0.25);
  });
});