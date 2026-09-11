import * as THREE from "three";
import { damp, yawToward } from "../core/math";
import type { CollisionWorld } from "../world/CollisionWorld";
import { createHumanoid } from "../world/prefabs";

export class Pedestrian {
  readonly group = new THREE.Group();
  x: number;
  z: number;
  yaw = 0;
  health = 40;
  down = false;
  fleeing = false;
  private targetX: number;
  private targetZ: number;
  private wait = 0;
  private dangerX = 0;
  private dangerZ = 0;
  radius = 0.4;

  constructor(x: number, z: number, body: number, accent: number) {
    this.x = x;
    this.z = z;
    this.targetX = x;
    this.targetZ = z;
    this.group.add(createHumanoid({ body, accent, pants: 0x22262c }));
    this.sync();
  }

  reset(x: number, z: number): void {
    this.x = x;
    this.z = z;
    this.targetX = x;
    this.targetZ = z;
    this.health = 40;
    this.down = false;
    this.fleeing = false;
    this.wait = 0;
    this.group.visible = true;
    this.group.rotation.x = 0;
    this.sync();
  }

  scare(x: number, z: number): void {
    if (this.down) return;
    this.fleeing = true;
    this.dangerX = x;
    this.dangerZ = z;
  }

  hit(amount: number): boolean {
    if (this.down) return false;
    this.health -= amount;
    if (this.health <= 0) {
      this.down = true;
      this.group.rotation.x = Math.PI / 2;
      this.group.position.y = 0.25;
      return true;
    }
    this.scare(this.x, this.z);
    return false;
  }

  update(
    dt: number,
    collision: CollisionWorld,
    sidewalks: { x: number; z: number }[],
    threatX: number,
    threatZ: number,
    threatSpeed: number
  ): void {
    if (this.down) return;
    if (Math.hypot(this.x - threatX, this.z - threatZ) < 7 && threatSpeed > 8) {
      this.scare(threatX, threatZ);
    }
    if (this.fleeing) {
      const away = yawToward(threatX, threatZ, this.x, this.z);
      const nx = this.x + Math.sin(away) * 7.8 * dt;
      const nz = this.z + Math.cos(away) * 7.8 * dt;
      const moved = collision.moveCircle(this.x, this.z, this.radius, nx - this.x, nz - this.z);
      this.x = moved.x;
      this.z = moved.z;
      this.yaw = away;
      if (Math.hypot(this.x - this.dangerX, this.z - this.dangerZ) > 28) this.fleeing = false;
    } else {
      this.wait -= dt;
      if (this.wait <= 0 && Math.hypot(this.x - this.targetX, this.z - this.targetZ) < 1.2) {
        const next = sidewalks[Math.floor(Math.random() * sidewalks.length)];
        if (next) {
          this.targetX = next.x;
          this.targetZ = next.z;
        }
        this.wait = 0.4 + Math.random() * 2.2;
      }
      const desired = yawToward(this.x, this.z, this.targetX, this.targetZ);
      this.yaw += (desired - this.yaw) * Math.min(1, dt * 4);
      const moved = collision.moveCircle(
        this.x,
        this.z,
        this.radius,
        Math.sin(this.yaw) * 1.55 * dt,
        Math.cos(this.yaw) * 1.55 * dt
      );
      this.x = moved.x;
      this.z = moved.z;
    }
    this.group.rotation.y = damp(this.group.rotation.y, this.yaw, 8, dt);
    this.sync();
  }

  private sync(): void {
    this.group.position.set(this.x, this.down ? 0.25 : 0, this.z);
  }
}

export function randomPedColors(): { body: number; accent: number } {
  const bodies = [0x2b3340, 0x3a2a32, 0x24382e, 0x403528, 0x2a2f3a];
  const accents = [0x5ef2e3, 0xff4d9a, 0xffc857, 0x7aa8ff, 0x7cffb2];
  return {
    body: bodies[Math.floor(Math.random() * bodies.length)]!,
    accent: accents[Math.floor(Math.random() * accents.length)]!
  };
}
