import * as THREE from "three";
import { clamp, damp } from "../core/math";
import type { Player } from "../player/Player";
import type { Vehicle } from "../vehicles/Vehicle";

export class GameCamera {
  yaw = 0.35;
  pitch = 0.32;
  private current = new THREE.Vector3(0, 6, -12);

  applyLook(dx: number, dy: number, sensitivity: number): void {
    this.yaw -= dx * 0.0022 * sensitivity;
    this.pitch = clamp(this.pitch + dy * 0.0018 * sensitivity, 0.08, 1.15);
  }

  update(dt: number, camera: THREE.PerspectiveCamera, player: Player, vehicle: Vehicle | null): void {
    const driving = Boolean(vehicle);
    const targetX = driving ? vehicle!.x : player.x;
    const targetZ = driving ? vehicle!.z : player.z;
    const targetY = driving ? 1.15 : 1.45;
    const dist = driving ? 10.5 : 6.6;
    const lookYaw = driving ? damp(this.yaw, vehicle!.heading, 1.6, dt) : this.yaw;
    if (driving) this.yaw = lookYaw;
    const ox = Math.sin(this.yaw) * Math.cos(this.pitch) * dist;
    const oz = Math.cos(this.yaw) * Math.cos(this.pitch) * dist;
    const oy = Math.sin(this.pitch) * dist + (driving ? 1.6 : 1.2);
    const desired = new THREE.Vector3(targetX - ox, targetY + oy, targetZ - oz);
    this.current.lerp(desired, 1 - Math.exp(-(driving ? 8 : 10) * dt));
    camera.position.copy(this.current);
    camera.lookAt(targetX, targetY + 0.4, targetZ);
  }
}
