import { describe, expect, it } from "vitest";
import { WantedSystem } from "./WantedSystem";

describe("WantedSystem", () => {
  it("raises heat from crimes and reports a 0-5 level", () => {
    const wanted = new WantedSystem();
    wanted.report("discharge", 0, 0);
    expect(wanted.level).toBe(1);
    wanted.report("watchDown", 1, 1);
    expect(wanted.level).toBeGreaterThanOrEqual(2);
    wanted.setAtLeast(5, 0, 0);
    expect(wanted.level).toBe(5);
  });

  it("decays after the player stays unseen and leaves last known", () => {
    const wanted = new WantedSystem();
    wanted.setAtLeast(3, 0, 0);
    wanted.update(8, false, 80, 80, 50, 16);
    wanted.update(6, false, 90, 90, 50, 16);
    expect(wanted.heat).toBeLessThan(3);
  });

  it("does not decay while currently seen", () => {
    const wanted = new WantedSystem();
    wanted.setAtLeast(2, 0, 0);
    wanted.update(20, true, 4, 4);
    expect(wanted.level).toBeGreaterThanOrEqual(2);
    expect(wanted.lastKnown?.x).toBe(4);
  });
});
