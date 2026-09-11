import { describe, expect, it } from "vitest";
import { angleDelta, clamp, forwardX, forwardZ, wrapAngle } from "./math";

describe("math helpers", () => {
  it("clamps to the inclusive range", () => {
    expect(clamp(3, 0, 2)).toBe(2);
    expect(clamp(-1, 0, 2)).toBe(0);
    expect(clamp(1, 0, 2)).toBe(1);
  });

  it("wraps angles onto [-PI, PI]", () => {
    expect(wrapAngle(Math.PI * 3)).toBeCloseTo(-Math.PI, 5);
    expect(wrapAngle(-Math.PI * 3)).toBeCloseTo(-Math.PI, 5);
    expect(Math.abs(wrapAngle(Math.PI * 2))).toBeCloseTo(0, 5);
  });

  it("reports the shortest angle delta", () => {
    expect(angleDelta(2.8, -2.8)).toBeGreaterThan(0);
    expect(Math.abs(angleDelta(2.8, -2.8))).toBeLessThan(Math.PI);
    expect(Math.abs(angleDelta(0, Math.PI))).toBeCloseTo(Math.PI, 5);
  });

  it("uses north-positive forward", () => {
    expect(forwardX(0)).toBeCloseTo(0, 5);
    expect(forwardZ(0)).toBeCloseTo(1, 5);
    expect(forwardX(Math.PI / 2)).toBeCloseTo(1, 5);
  });
});
