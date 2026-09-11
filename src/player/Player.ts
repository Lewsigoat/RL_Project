import * as THREE from "three";
import { PLAYER_RADIUS, PLAYER_SPRINT, PLAYER_WALK } from "../core/types";
import { clamp, damp, forwardX, forwardZ } from "../core/math";
import type { Input } from "../input/Input";
import type { CollisionWorld } from "../world/CollisionWorld";
import { createHumanoid } from "../world/prefabs";

export class Player {
  readonly group = new THREE.Group();
  readonly mesh: THREE.Group;
  x = 4;
  y = 0;
  z = -18;
  vx = 0;
  vz = 0;
  vy = 0;
  yaw = 0;
  grounded = true;
  health = 100;
  inVehicle = false;
  radius = PLAYER_RADIUS;
  private bob = 0;

  constructor() {
    this.mesh = createHumanoid({ body: 0x1c2a34, accent: 0x5ef2e3, pants: 0x14181c });
    this.group.add(this.mesh);
    this.sync();
  }

  reset(): void {
    this.x = 4;
    this.y = 0;
    this.z = -18;
    this.vx = 0;
    this.vz = 0;
    this.vy = 0;
    this.yaw = 0;
    this.health = 100;
    this.inVehicle = false;
    this.grounded = true;
    this.group.visible = true;
    this.sync();
  }

  damage(amount: number): void {
    this.health = clamp(this.health - amount, 0, 100);
  }

  update(dt: number, input: Input, camYaw: number, collision: CollisionWorld): void {
    if (this.inVehicle) {
      this.group.visible = false;
      return;
    }
    this.group.visible = true;
    const axis = input.axis();
    const speed = input.sprint() ? PLAYER_SPRINT : PLAYER_WALK;
    const fx = forwardX(camYaw);
    const fz = forwardZ(camYaw);
    const rx = forwardX(camYaw + Math.PI / 2);
    const rz = forwardZ(camYaw + Math.PI / 2);
    const wishX = fx * axis.y + rx * axis.x;
    const wishZ = fz * axis.y + rz * axis.x;
    const moving = Math.hypot(wishX, wishZ) > 0.08;
    const accel = this.grounded ? 34 : 10;
    const drag = this.grounded ? 10 : 1.4;
    this.vx += wishX * accel * dt;
    this.vz += wishZ * accel * dt;
    this.vx -= this.vx * drag * dt;
    this.vz -= this.vz * drag * dt;
    const max = moving ? speed : speed * 0.35;
    const mag = Math.hypot(this.vx, this.vz);
    if (mag > max) {
      this.vx *= max / mag;
      this.vz *= max / mag;
    }
    if (this.grounded && input.jump()) {
      this.vy = 7.4;
      this.grounded = false;
    }
    this.vy -= 22 * dt;
    this.y += this.vy * dt;
    if (this.y <= 0) {
      this.y = 0;
      this.vy = 0;
      this.grounded = true;
    }

    const moved = collision.moveCircle(this.x, this.z, this.radius, this.vx * dt, this.vz * dt);
    this.x = moved.x;
    this.z = moved.z;
    if (moved.hit) {
      this.vx *= 0.35;
      this.vz *= 0.35;
    }
    if (moving) this.yaw = Math.atan2(wishX, wishZ);
    this.bob += dt * (moving ? 10 : 2);
    this.mesh.position.y = this.grounded && moving ? Math.abs(Math.sin(this.bob)) * 0.05 : 0;
    this.group.rotation.y = damp(this.group.rotation.y, this.yaw, 12, dt);
    this.sync();
  }

  setPosition(x: number, z: number, yaw: number): void {
    this.x = x;
    this.z = z;
    this.y = 0;
    this.yaw = yaw;
    this.sync();
  }

  private sync(): void {
    this.group.position.set(this.x, this.y, this.z);
  }
}
