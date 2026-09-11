import { describe, expect, it } from "vitest";
import { defaultSave } from "../core/types";
import { loadSave, mergeSave } from "./SaveStore";

describe("SaveStore", () => {
  it("returns a safe default when storage is empty or unavailable", () => {
    const data = loadSave();
    expect(data.version).toBe(1);
    expect(data.money).toBeGreaterThanOrEqual(0);
    expect(data.mouseSensitivity).toBeGreaterThan(0);
  });

  it("merges patches without dropping required fields", () => {
    const next = mergeSave(defaultSave(), { money: 2500, missionCompleted: true });
    expect(next.money).toBe(2500);
    expect(next.missionCompleted).toBe(true);
    expect(next.version).toBe(1);
    expect(next.volume).toBeGreaterThan(0);
  });
});
