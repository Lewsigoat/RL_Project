import * as THREE from "three";
import { clamp } from "../core/math";

export class DayNight {
  /** 0 midnight, 0.25 dawn, 0.5 noon, 0.75 dusk */
  cycle = 0.78;
  readonly period = 220;

  update(dt: number): void {
    this.cycle = (this.cycle + dt / this.period) % 1;
  }

  get nightFactor(): number {
    const t = this.cycle;
    if (t < 0.22 || t > 0.78) return 1;
    if (t < 0.32) return 1 - (t - 0.22) / 0.1;
    if (t > 0.68) return (t - 0.68) / 0.1;
    return 0;
  }

  label(): string {
    const t = this.cycle;
    if (t < 0.2) return "Night";
    if (t < 0.3) return "Dawn";
    if (t < 0.45) return "Morning";
    if (t < 0.58) return "Noon";
    if (t < 0.7) return "Afternoon";
    if (t < 0.8) return "Dusk";
    return "Night";
  }

  apply(
    sun: THREE.DirectionalLight,
    hemi: THREE.HemisphereLight,
    scene: THREE.Scene,
    fog: THREE.Fog,
    neonMats: THREE.MeshStandardMaterial[],
    windowMats: THREE.MeshStandardMaterial[]
  ): void {
    const night = this.nightFactor;
    const day = 1 - night;
    const elev = (this.cycle - 0.25) * Math.PI * 2;
    sun.position.set(Math.cos(elev) * 70, Math.sin(elev) * 55 + 8, 28);
    sun.intensity = 0.18 + day * 1.15;
    sun.color.setHSL(0.08 + day * 0.04, 0.35, 0.82);
    hemi.intensity = 0.22 + day * 0.55;
    hemi.color.set(night > 0.6 ? 0x1a2740 : 0xcfe6ff);
    hemi.groundColor.set(night > 0.6 ? 0x0b0f14 : 0x3a4038);
    const sky = new THREE.Color().lerpColors(new THREE.Color(0x9ec8e8), new THREE.Color(0x071018), night);
    scene.background = sky;
    fog.color.copy(sky);
    fog.near = 38;
    fog.far = 118 + day * 20;
    const neon = 0.35 + night * 1.4;
    for (const mat of neonMats) mat.emissiveIntensity = neon;
    const windows = 0.08 + night * 1.15;
    for (const mat of windowMats) mat.emissiveIntensity = windows;
  }

  cloudOffset(elapsed: number): number {
    return (elapsed * 0.004 + this.cycle) % 1;
  }
}

export function toneExposure(night: number): number {
  return clamp(0.92 + night * 0.18, 0.85, 1.2);
}
