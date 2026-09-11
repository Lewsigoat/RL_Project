import { SAVE_KEY, defaultSave, type SaveData } from "../core/types";
import { clamp } from "../core/math";

export function loadSave(): SaveData {
  try {
    const raw = localStorage.getItem(SAVE_KEY);
    if (!raw) return defaultSave();
    const parsed = JSON.parse(raw) as Partial<SaveData>;
    const base = defaultSave();
    return {
      version: 1,
      money: clamp(Number(parsed.money ?? base.money), 0, 999999),
      missionCompleted: Boolean(parsed.missionCompleted),
      mouseSensitivity: clamp(Number(parsed.mouseSensitivity ?? base.mouseSensitivity), 0.2, 2.2),
      volume: clamp(Number(parsed.volume ?? base.volume), 0, 1),
      bestWanted: clamp(Number(parsed.bestWanted ?? 0), 0, 5)
    };
  } catch {
    return defaultSave();
  }
}

export function writeSave(data: SaveData): void {
  try {
    localStorage.setItem(SAVE_KEY, JSON.stringify(data));
  } catch {
    // Private mode or quota — game still runs.
  }
}

export function mergeSave(current: SaveData, patch: Partial<SaveData>): SaveData {
  const next = { ...current, ...patch, version: 1 as const };
  writeSave(next);
  return next;
}
