export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

export function damp(current: number, target: number, lambda: number, dt: number): number {
  return lerp(current, target, 1 - Math.exp(-lambda * dt));
}

export function wrapAngle(radians: number): number {
  const tau = Math.PI * 2;
  return ((((radians + Math.PI) % tau) + tau) % tau) - Math.PI;
}

export function angleDelta(from: number, to: number): number {
  return wrapAngle(to - from);
}

export function hypot2(x: number, z: number): number {
  return Math.hypot(x, z);
}

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function pick<T>(rng: () => number, items: readonly T[]): T {
  return items[Math.floor(rng() * items.length)]!;
}

export function yawToward(fromX: number, fromZ: number, toX: number, toZ: number): number {
  return Math.atan2(toX - fromX, toZ - fromZ);
}

export function forwardX(yaw: number): number {
  return Math.sin(yaw);
}

export function forwardZ(yaw: number): number {
  return Math.cos(yaw);
}
