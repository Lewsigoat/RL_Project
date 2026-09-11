import { describe, expect, it } from "vitest";
import { CollisionWorld, rayAabb } from "./CollisionWorld";

describe("CollisionWorld", () => {
  it("slides a circle out of a static box", () => {
    const world = new CollisionWorld();
    world.addBox(0, 0, 2, 2);
    const moved = world.moveCircle(-3, 0, 0.5, 2.2, 0);
    expect(moved.hit).toBe(true);
    expect(moved.x).toBeLessThanOrEqual(-2.5);
  });

  it("keeps movement free when the path is open", () => {
    const world = new CollisionWorld();
    world.addBox(10, 10, 1, 1);
    const moved = world.moveCircle(0, 0, 0.4, 1, 0);
    expect(moved.hit).toBe(false);
    expect(moved.x).toBeCloseTo(1, 5);
  });

  it("blocks line of sight through a building", () => {
    const world = new CollisionWorld();
    world.addBox(0, 0, 2, 2);
    expect(world.losClear(-6, 0, 6, 0)).toBe(false);
    expect(world.losClear(-6, 8, 6, 8)).toBe(true);
  });

  it("hits an AABB along a ray", () => {
    const t = rayAabb(-4, 0, 1, 0, { minX: -1, maxX: 1, minZ: -1, maxZ: 1, minY: 0, maxY: 4 }, 20);
    expect(t).toBeGreaterThan(0);
    expect(t).toBeCloseTo(3, 4);
  });
});
