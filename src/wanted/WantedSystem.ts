import { clamp } from "../core/math";

export type CrimeKind =
  | "discharge"
  | "assault"
  | "vehicular"
  | "watchHit"
  | "watchDown"
  | "ramWatch"
  | "vandal";

export interface LastKnown {
  x: number;
  z: number;
  age: number;
}

export class WantedSystem {
  heat = 0;
  unseen = 0;
  lastKnown: LastKnown | null = null;
  readonly maxLevel = 5;

  get level(): number {
    if (this.heat <= 0) return 0;
    return clamp(Math.max(1, Math.floor(this.heat)), 1, this.maxLevel);
  }

  reset(): void {
    this.heat = 0;
    this.unseen = 0;
    this.lastKnown = null;
  }

  report(kind: CrimeKind, x: number, z: number): void {
    const add =
      kind === "watchDown"
        ? 2.15
        : kind === "watchHit" || kind === "ramWatch"
          ? 1.35
          : kind === "vehicular"
            ? 1.45
            : kind === "assault"
              ? 1.15
              : kind === "discharge"
                ? 0.85
                : 0.4;
    this.heat = clamp(this.heat + add, 0, this.maxLevel);
    this.markSeen(x, z);
  }

  setAtLeast(level: number, x: number, z: number): void {
    this.heat = clamp(Math.max(this.heat, level), 0, this.maxLevel);
    this.markSeen(x, z);
  }

  markSeen(x: number, z: number): void {
    this.lastKnown = { x, z, age: 0 };
    this.unseen = 0;
  }

  update(dt: number, seen: boolean, x: number, z: number): void {
    if (this.heat <= 0) {
      this.heat = 0;
      this.unseen = 0;
      if (!seen) this.lastKnown = null;
      return;
    }
    if (seen) {
      this.markSeen(x, z);
      return;
    }
    this.unseen += dt;
    if (this.lastKnown) this.lastKnown.age += dt;
    if (this.unseen < 11) return;
    const far =
      !this.lastKnown || Math.hypot(x - this.lastKnown.x, z - this.lastKnown.z) > 28;
    if (!far && this.unseen < 18) return;
    this.heat = clamp(this.heat - dt * 0.22, 0, this.maxLevel);
    if (this.heat < 0.05) this.reset();
  }
}

export function crimeLabel(kind: CrimeKind): string {
  switch (kind) {
    case "discharge":
      return "Weapons fire";
    case "assault":
      return "Assault";
    case "vehicular":
      return "Reckless impact";
    case "watchHit":
      return "Watch engaged";
    case "watchDown":
      return "Watch officer down";
    case "ramWatch":
      return "Watch vehicle struck";
    default:
      return "Street damage";
  }
}
