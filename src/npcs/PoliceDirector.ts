import * as THREE from "three";
import { ROAD_COORDS } from "../core/types";
import { yawToward } from "../core/math";
import type { CollisionWorld } from "../world/CollisionWorld";
import { createHumanoid } from "../world/prefabs";
import { Vehicle } from "../vehicles/Vehicle";

export interface PoliceFoot {
  group: THREE.Group;
  x: number;
  z: number;
  yaw: number;
  health: number;
  down: boolean;
  arrest: number;
  shootCd: number;
  radius: number;
}

export class PoliceDirector {
  readonly feet: PoliceFoot[] = [];
  readonly cars: Vehicle[] = [];
  readonly group = new THREE.Group();
  private spawnPoints: { x: number; z: number }[] = [];

  constructor() {
    for (const c of ROAD_COORDS) {
      this.spawnPoints.push({ x: c, z: -88 }, { x: c, z: 88 }, { x: -88, z: c }, { x: 88, z: c });
    }
    for (let i = 0; i < 4; i += 1) {
      const group = new THREE.Group();
      group.add(createHumanoid({ body: 0x15202c, accent: 0x5ef2e3, pants: 0x0e141a, watch: true }));
      group.visible = false;
      this.group.add(group);
      this.feet.push({
        group,
        x: 90,
        z: 90,
        yaw: 0,
        health: 80,
        down: true,
        arrest: 0,
        shootCd: 0,
        radius: 0.42
      });
    }
    for (let i = 0; i < 3; i += 1) {
      const car = new Vehicle(`watch-${i}`, "watch", 92, 92, 0, 0x101820, 0x5ef2e3);
      car.group.visible = false;
      car.traffic = false;
      this.cars.push(car);
      this.group.add(car.group);
    }
  }

  reset(): void {
    for (const foot of this.feet) this.deactivateFoot(foot);
    for (const car of this.cars) this.deactivateCar(car);
  }

  update(opts: {
    dt: number;
    wanted: number;
    playerX: number;
    playerZ: number;
    playerSpeed: number;
    onFoot: boolean;
    lastKnown: { x: number; z: number } | null;
    collision: CollisionWorld;
    vehicles: Vehicle[];
  }): { seen: boolean; arresting: boolean; shots: { x: number; z: number }[] } {
    const needFoot = opts.wanted >= 1 ? Math.min(4, opts.wanted + 1) : 0;
    const needCar = opts.wanted >= 2 ? Math.min(3, opts.wanted - 1) : 0;
    this.ensureCount(needFoot, needCar, opts.playerX, opts.playerZ);

    const target = opts.lastKnown ?? { x: opts.playerX, z: opts.playerZ };
    let seen = false;
    let arresting = false;
    const shots: { x: number; z: number }[] = [];

    for (const foot of this.feet) {
      if (foot.down || !foot.group.visible) continue;
      const dist = Math.hypot(foot.x - opts.playerX, foot.z - opts.playerZ);
      const los = dist < 42 && opts.collision.losClear(foot.x, foot.z, opts.playerX, opts.playerZ);
      if (los) seen = true;
      const aim = los ? { x: opts.playerX, z: opts.playerZ } : target;
      const desired = yawToward(foot.x, foot.z, aim.x, aim.z);
      foot.yaw = desired;
      const run = 5.6 + opts.wanted * 0.35;
      const moved = opts.collision.moveCircle(
        foot.x,
        foot.z,
        foot.radius,
        Math.sin(foot.yaw) * run * opts.dt,
        Math.cos(foot.yaw) * run * opts.dt
      );
      foot.x = moved.x;
      foot.z = moved.z;
      foot.group.position.set(foot.x, 0, foot.z);
      foot.group.rotation.y = foot.yaw;
      foot.shootCd -= opts.dt;
      if (los && dist < 16 && foot.shootCd <= 0) {
        foot.shootCd = 0.85;
        shots.push({ x: foot.x, z: foot.z });
      }
      if (opts.onFoot && dist < 1.85 && opts.playerSpeed < 3.4) {
        foot.arrest += opts.dt;
        if (foot.arrest > 1.35) arresting = true;
      } else {
        foot.arrest = Math.max(0, foot.arrest - opts.dt);
      }
    }

    for (const car of this.cars) {
      if (!car.group.visible) continue;
      const dist = Math.hypot(car.x - opts.playerX, car.z - opts.playerZ);
      const los = dist < 55 && opts.collision.losClear(car.x, car.z, opts.playerX, opts.playerZ);
      if (los) seen = true;
      const aim = los ? { x: opts.playerX, z: opts.playerZ } : target;
      car.updateChase(opts.dt, aim.x, aim.z, opts.collision, opts.vehicles);
    }

    if (opts.wanted <= 0) this.reset();
    return { seen, arresting, shots };
  }

  hitFoot(foot: PoliceFoot, amount: number): "hit" | "down" | null {
    if (foot.down || !foot.group.visible) return null;
    foot.health -= amount;
    if (foot.health <= 0) {
      foot.down = true;
      foot.group.rotation.x = Math.PI / 2;
      foot.group.position.y = 0.25;
      return "down";
    }
    return "hit";
  }

  private ensureCount(feet: number, cars: number, px: number, pz: number): void {
    let activeF = this.feet.filter((f) => f.group.visible && !f.down).length;
    let activeC = this.cars.filter((c) => c.group.visible).length;
    while (activeF < feet) {
      const slot = this.feet.find((f) => !f.group.visible || f.down);
      if (!slot) break;
      const p = this.farthestSpawn(px, pz);
      slot.x = p.x;
      slot.z = p.z;
      slot.health = 80;
      slot.down = false;
      slot.arrest = 0;
      slot.shootCd = 0.4;
      slot.group.visible = true;
      slot.group.rotation.x = 0;
      slot.group.position.set(slot.x, 0, slot.z);
      activeF += 1;
    }
    while (activeC < cars) {
      const slot = this.cars.find((c) => !c.group.visible);
      if (!slot) break;
      const p = this.farthestSpawn(px, pz);
      slot.x = p.x;
      slot.z = p.z;
      slot.heading = yawToward(p.x, p.z, px, pz);
      slot.speed = 8;
      slot.health = 100;
      slot.group.visible = true;
      slot.group.position.set(slot.x, 0, slot.z);
      activeC += 1;
    }
  }

  private farthestSpawn(px: number, pz: number): { x: number; z: number } {
    let best = this.spawnPoints[0]!;
    let bestD = -1;
    for (const p of this.spawnPoints) {
      const d = Math.hypot(p.x - px, p.z - pz);
      if (d > 32 && d > bestD) {
        best = p;
        bestD = d;
      }
    }
    return best;
  }

  private deactivateFoot(foot: PoliceFoot): void {
    foot.down = true;
    foot.group.visible = false;
    foot.arrest = 0;
    foot.x = 90;
    foot.z = 90;
  }

  private deactivateCar(car: Vehicle): void {
    car.group.visible = false;
    car.x = 92;
    car.z = 92;
    car.speed = 0;
  }
}
