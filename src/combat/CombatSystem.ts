import * as THREE from "three";
import type { CollisionWorld } from "../world/CollisionWorld";
import type { Pedestrian } from "../npcs/Pedestrian";
import type { PoliceDirector } from "../npcs/PoliceDirector";
import type { Vehicle } from "../vehicles/Vehicle";
import type { WantedSystem } from "../wanted/WantedSystem";
import type { Player } from "../player/Player";

export interface CombatEvent {
  hit: boolean;
  kind?: "ped" | "watch" | "vehicle" | "world";
}

export class CombatSystem {
  cooldown = 0;
  private pool: THREE.Line[] = [];

  constructor(private readonly scene: THREE.Scene) {
    const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3(0, 0, -1)]);
    const mat = new THREE.LineBasicMaterial({ color: 0xffe08a, transparent: true, opacity: 0.8 });
    for (let i = 0; i < 8; i += 1) {
      const line = new THREE.Line(geo.clone(), mat.clone());
      line.visible = false;
      this.scene.add(line);
      this.pool.push(line);
    }
  }

  update(dt: number): void {
    this.cooldown = Math.max(0, this.cooldown - dt);
    for (const line of this.pool) {
      if (!line.visible) continue;
      const mat = line.material as THREE.LineBasicMaterial;
      mat.opacity -= dt * 4;
      if (mat.opacity <= 0) {
        line.visible = false;
        mat.opacity = 0.8;
      }
    }
  }

  tryFire(opts: {
    origin: THREE.Vector3;
    dir: THREE.Vector3;
    player: Player;
    peds: Pedestrian[];
    police: PoliceDirector;
    vehicles: Vehicle[];
    collision: CollisionWorld;
    wanted: WantedSystem;
  }): CombatEvent {
    if (this.cooldown > 0) return { hit: false };
    this.cooldown = 0.22;
    const dir = opts.dir.clone().normalize();
    const max = 48;
    const worldHit = opts.collision.rayHit(opts.origin.x, opts.origin.z, dir.x, dir.z, max);
    let best = worldHit > 0 ? worldHit : max;
    let kind: CombatEvent["kind"] = worldHit > 0 ? "world" : undefined;
    let pedHit: Pedestrian | null = null;
    let watchIndex = -1;
    let vehHit: Vehicle | null = null;

    for (const ped of opts.peds) {
      if (ped.down) continue;
      const t = rayCircle(opts.origin.x, opts.origin.z, dir.x, dir.z, ped.x, ped.z, 0.55, best);
      if (t >= 0) {
        best = t;
        kind = "ped";
        pedHit = ped;
      }
    }
    for (let i = 0; i < opts.police.feet.length; i += 1) {
      const foot = opts.police.feet[i]!;
      if (foot.down || !foot.group.visible) continue;
      const t = rayCircle(opts.origin.x, opts.origin.z, dir.x, dir.z, foot.x, foot.z, 0.55, best);
      if (t >= 0) {
        best = t;
        kind = "watch";
        watchIndex = i;
        pedHit = null;
      }
    }
    for (const veh of opts.vehicles) {
      if (!veh.group.visible) continue;
      const t = rayCircle(opts.origin.x, opts.origin.z, dir.x, dir.z, veh.x, veh.z, veh.radius, best);
      if (t >= 0 && t > 1.2) {
        best = t;
        kind = "vehicle";
        vehHit = veh;
        pedHit = null;
        watchIndex = -1;
      }
    }

    const end = opts.origin.clone().addScaledVector(dir, best);
    this.flash(opts.origin, end);

    if (kind === "ped" && pedHit) {
      const down = pedHit.hit(34);
      opts.wanted.report(down ? "assault" : "discharge", opts.player.x, opts.player.z);
      return { hit: true, kind };
    }
    if (kind === "watch" && watchIndex >= 0) {
      const result = opts.police.hitFoot(opts.police.feet[watchIndex]!, 34);
      opts.wanted.report(result === "down" ? "watchDown" : "watchHit", opts.player.x, opts.player.z);
      return { hit: true, kind };
    }
    if (kind === "vehicle" && vehHit) {
      vehHit.health -= 18;
      opts.wanted.report(vehHit.kind === "watch" ? "ramWatch" : "vandal", opts.player.x, opts.player.z);
      return { hit: true, kind };
    }
    opts.wanted.report("discharge", opts.player.x, opts.player.z);
    return { hit: Boolean(kind), kind };
  }

  private flash(from: THREE.Vector3, to: THREE.Vector3): void {
    const line = this.pool.find((l) => !l.visible) ?? this.pool[0]!;
    const pos = line.geometry.getAttribute("position") as THREE.BufferAttribute;
    pos.setXYZ(0, from.x, from.y, from.z);
    pos.setXYZ(1, to.x, to.y, to.z);
    pos.needsUpdate = true;
    (line.material as THREE.LineBasicMaterial).opacity = 0.85;
    line.visible = true;
  }
}

function rayCircle(
  ox: number,
  oz: number,
  dx: number,
  dz: number,
  cx: number,
  cz: number,
  r: number,
  max: number
): number {
  const fx = ox - cx;
  const fz = oz - cz;
  const b = fx * dx + fz * dz;
  const c = fx * fx + fz * fz - r * r;
  const disc = b * b - c;
  if (disc < 0) return -1;
  const t = -b - Math.sqrt(disc);
  if (t < 0 || t > max) return -1;
  return t;
}
