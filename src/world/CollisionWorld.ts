import { CITY_HALF, type AABB } from "../core/types";
import { clamp } from "../core/math";

export class CollisionWorld {
  readonly statics: AABB[] = [];

  addBox(cx: number, cz: number, hx: number, hz: number, minY = 0, maxY = 12): AABB {
    const box: AABB = {
      minX: cx - hx,
      maxX: cx + hx,
      minZ: cz - hz,
      maxZ: cz + hz,
      minY,
      maxY
    };
    this.statics.push(box);
    return box;
  }

  addAABB(box: AABB): void {
    this.statics.push(box);
  }

  moveCircle(
    x: number,
    z: number,
    radius: number,
    dx: number,
    dz: number
  ): { x: number; z: number; hit: boolean } {
    let nx = x + dx;
    let nz = z + dz;
    let hit = false;

    for (let iter = 0; iter < 4; iter += 1) {
      let pushed = false;
      for (const box of this.statics) {
        const nearestX = clamp(nx, box.minX, box.maxX);
        const nearestZ = clamp(nz, box.minZ, box.maxZ);
        let ox = nx - nearestX;
        let oz = nz - nearestZ;
        const d2 = ox * ox + oz * oz;
        if (d2 >= radius * radius) continue;
        hit = true;
        pushed = true;
        if (d2 < 1e-8) {
          const left = nx - box.minX;
          const right = box.maxX - nx;
          const south = nz - box.minZ;
          const north = box.maxZ - nz;
          const smallest = Math.min(left, right, south, north);
          if (smallest === left) nx = box.minX - radius;
          else if (smallest === right) nx = box.maxX + radius;
          else if (smallest === south) nz = box.minZ - radius;
          else nz = box.maxZ + radius;
        } else {
          const d = Math.sqrt(d2);
          const push = (radius - d) / d;
          nx += ox * push;
          nz += oz * push;
        }
      }
      if (!pushed) break;
    }

    const limit = CITY_HALF - 1.15;
    nx = clamp(nx, -limit, limit);
    nz = clamp(nz, -limit, limit);
    return { x: nx, z: nz, hit };
  }

  rayHit(ox: number, oz: number, dirX: number, dirZ: number, maxDist: number): number {
    let best = maxDist + 1;
    let found = false;
    for (const box of this.statics) {
      const t = rayAabb(ox, oz, dirX, dirZ, box, maxDist);
      if (t >= 0 && t < best) {
        best = t;
        found = true;
      }
    }
    return found ? best : -1;
  }

  losClear(ax: number, az: number, bx: number, bz: number): boolean {
    const dx = bx - ax;
    const dz = bz - az;
    const dist = Math.hypot(dx, dz);
    if (dist < 0.05) return true;
    const hit = this.rayHit(ax, az, dx / dist, dz / dist, dist);
    return hit < 0 || hit > dist - 0.55;
  }
}

export function rayAabb(
  ox: number,
  oz: number,
  dirX: number,
  dirZ: number,
  box: AABB,
  maxDist: number
): number {
  const invX = dirX === 0 ? 1e9 : 1 / dirX;
  const invZ = dirZ === 0 ? 1e9 : 1 / dirZ;
  let t1 = (box.minX - ox) * invX;
  let t2 = (box.maxX - ox) * invX;
  let t3 = (box.minZ - oz) * invZ;
  let t4 = (box.maxZ - oz) * invZ;
  const tmin = Math.max(Math.min(t1, t2), Math.min(t3, t4));
  const tmax = Math.min(Math.max(t1, t2), Math.max(t3, t4));
  if (tmax < 0 || tmin > tmax || tmin > maxDist) return -1;
  return tmin < 0 ? 0 : tmin;
}

export function circlesOverlap(
  ax: number,
  az: number,
  ar: number,
  bx: number,
  bz: number,
  br: number
): boolean {
  const dx = ax - bx;
  const dz = az - bz;
  const r = ar + br;
  return dx * dx + dz * dz < r * r;
}

export function separateCircles(
  ax: number,
  az: number,
  ar: number,
  bx: number,
  bz: number,
  br: number
): { ax: number; az: number; bx: number; bz: number } | null {
  const dx = ax - bx;
  const dz = az - bz;
  const dist = Math.hypot(dx, dz);
  const min = ar + br;
  if (dist >= min) return null;
  if (dist < 1e-5) {
    return { ax: ax + min * 0.5, az, bx: bx - min * 0.5, bz };
  }
  const push = (min - dist) / dist;
  return {
    ax: ax + dx * push * 0.5,
    az: az + dz * push * 0.5,
    bx: bx - dx * push * 0.5,
    bz: bz - dz * push * 0.5
  };
}
