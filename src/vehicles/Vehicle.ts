import * as THREE from "three";
import { angleDelta, clamp, damp, forwardX, forwardZ } from "../core/math";
import type { Input } from "../input/Input";
import { CollisionWorld, separateCircles } from "../world/CollisionWorld";
import { createVehicleMesh, type VehicleKind } from "../world/prefabs";

export class Vehicle {
  readonly group = new THREE.Group();
  id: string;
  kind: VehicleKind;
  x: number;
  z: number;
  heading: number;
  speed = 0;
  radius: number;
  occupied = false;
  traffic = false;
  health = 100;
  color: number;
  private spawnX: number;
  private spawnZ: number;
  private spawnH: number;
  private loop: { x: number; z: number }[] = [];
  private loopIndex = 0;

  constructor(id: string, kind: VehicleKind, x: number, z: number, heading: number, paint: number, accent: number) {
    this.id = id;
    this.kind = kind;
    this.x = x;
    this.z = z;
    this.heading = heading;
    this.spawnX = x;
    this.spawnZ = z;
    this.spawnH = heading;
    this.color = paint;
    this.radius = kind === "hauler" || kind === "van" ? 2.15 : 1.85;
    this.group.add(createVehicleMesh(kind, paint, accent));
    this.sync();
  }

  resetPark(): void {
    this.x = this.spawnX;
    this.z = this.spawnZ;
    this.heading = this.spawnH;
    this.speed = 0;
    this.occupied = false;
    this.health = 100;
    this.sync();
  }

  resetTraffic(): void {
    const node = this.loop[0];
    if (node) {
      this.x = node.x;
      this.z = node.z;
    }
    this.speed = 6;
    this.occupied = false;
    this.health = 100;
    this.traffic = true;
    this.loopIndex = 0;
    this.sync();
  }

  assignLoop(loop: { x: number; z: number }[], index = 0): void {
    this.traffic = true;
    this.loop = loop;
    this.loopIndex = index % loop.length;
  }

  updateDriven(dt: number, input: Input, collision: CollisionWorld, others: Vehicle[], camYaw: number): void {
    const axis = input.axis();
    const throttle = axis.y;
    const steer = -axis.x;
    const brake = input.jump();
    const max = this.kind === "van" || this.kind === "hauler" ? 24 : 30;
    if (throttle > 0) this.speed += throttle * 20 * dt;
    else if (throttle < 0) this.speed += throttle * 14 * dt;
    else this.speed -= Math.sign(this.speed) * 3.2 * dt;
    if (brake) this.speed -= Math.sign(this.speed) * 28 * dt;
    this.speed = clamp(this.speed, -10, max);
    if (Math.abs(throttle) > 0.05) {
      this.heading += angleDelta(this.heading, camYaw) * Math.min(1, dt * 2.8);
    }
    const steerScale = 2.15 * (1 - Math.min(0.72, Math.abs(this.speed) / max));
    this.heading += steer * steerScale * Math.sign(this.speed || 1) * dt * (brake ? 1.55 : 1);
    this.advance(dt, collision, others, 0.08);
  }

  updateTraffic(dt: number, collision: CollisionWorld, others: Vehicle[], playerX: number, playerZ: number, playerR: number): void {
    if (!this.loop.length) return;
    const target = this.loop[this.loopIndex]!;
    const dist = Math.hypot(target.x - this.x, target.z - this.z);
    if (dist < 4.5) this.loopIndex = (this.loopIndex + 1) % this.loop.length;
    const desired = Math.atan2(target.x - this.x, target.z - this.z);
    this.heading += angleDelta(this.heading, desired) * Math.min(1, dt * 2.4);
    let want = 9.5;
    const fx = forwardX(this.heading);
    const fz = forwardZ(this.heading);
    const lookX = this.x + fx * 9;
    const lookZ = this.z + fz * 9;
    if (Math.hypot(lookX - playerX, lookZ - playerZ) < 7 && playerR > 0.3) want = 0;
    for (const other of others) {
      if (other === this) continue;
      const ox = other.x - this.x;
      const oz = other.z - this.z;
      const ahead = ox * fx + oz * fz;
      if (ahead > 0 && ahead < 10 && Math.hypot(ox, oz) < 7.5) want = 0;
    }
    this.speed = damp(this.speed, want, 3.2, dt);
    this.advance(dt, collision, others, 0.08);
  }

  updateChase(dt: number, tx: number, tz: number, collision: CollisionWorld, others: Vehicle[]): void {
    const desired = Math.atan2(tx - this.x, tz - this.z);
    this.heading += angleDelta(this.heading, desired) * Math.min(1, dt * 2.8);
    this.speed = damp(this.speed, 22, 2.4, dt);
    this.advance(dt, collision, others, 0.18);
  }

  private advance(dt: number, collision: CollisionWorld, others: Vehicle[], bounce: number): void {
    const dx = forwardX(this.heading) * this.speed * dt;
    const dz = forwardZ(this.heading) * this.speed * dt;
    const moved = collision.moveCircle(this.x, this.z, this.radius, dx, dz);
    this.x = moved.x;
    this.z = moved.z;
    if (moved.hit) this.speed *= bounce > 0.1 ? -bounce : 0.35;
    for (const other of others) {
      if (other === this) continue;
      const sep = separateCircles(this.x, this.z, this.radius, other.x, other.z, other.radius);
      if (!sep) continue;
      this.x = sep.ax;
      this.z = sep.az;
      other.x = sep.bx;
      other.z = sep.bz;
      this.speed *= 0.55;
      other.speed *= 0.7;
    }
    this.sync();
  }

  kmh(): number {
    return Math.abs(this.speed) * 4.2;
  }

  label(): string {
    switch (this.id) {
      case "volt-runner":
        return "Volt Runner";
      case "ember-coupe":
        return "Ember Coupe";
      case "slate-hauler":
        return "Slate Hauler";
      case "pearl-cruiser":
        return "Pearl Cruiser";
      case "grid-taxi":
        return "Grid Taxi";
      default:
        return this.kind === "watch" ? "Watch Interceptor" : "Street car";
    }
  }

  private sync(): void {
    this.group.position.set(this.x, 0, this.z);
    this.group.rotation.y = this.heading;
  }
}
