import * as THREE from "three";
import { clamp } from "../core/math";

export class DayNight {
  /** 0 midnight, 0.25 dawn, 0.5 noon, 0.75 dusk */
  cycle = 0.71;
  readonly period = 220;

  update(dt: number): void {
    this.cycle = (this.cycle + dt / this.period) % 1;
  }

  get nightFactor(): number {
    const t = this.cycle;
    if (t < 0.2 || t > 0.82) return 1;
    if (t < 0.32) return 1 - (t - 0.2) / 0.12;
    if (t > 0.7) return (t - 0.7) / 0.12;
    return 0;
  }

  label(): string {
    const t = this.cycle;
    if (t < 0.2) return "Night";
    if (t < 0.3) return "Dawn";
    if (t < 0.45) return "Morning";
    if (t < 0.58) return "Noon";
    if (t < 0.7) return "Afternoon";
    if (t < 0.82) return "Dusk";
    return "Night";
  }

  apply(
    sun: THREE.DirectionalLight,
    hemi: THREE.HemisphereLight,
    fill: THREE.AmbientLight,
    scene: THREE.Scene,
    fog: THREE.Fog,
    neonMats: THREE.MeshStandardMaterial[],
    windowMats: THREE.MeshStandardMaterial[]
  ): void {
    const night = this.nightFactor;
    const day = 1 - night;
    const elev = (this.cycle - 0.25) * Math.PI * 2;
    const height = Math.max(18, Math.sin(elev) * 70 + 16);
    sun.position.set(Math.cos(elev) * 80, height, 36);
    sun.intensity = 0.55 + day * 1.35;
    sun.color.setHSL(0.08 + day * 0.05, 0.4, 0.86);
    sun.castShadow = night < 0.85;
    hemi.intensity = 0.7 + day * 0.5;
    hemi.color.set(night > 0.55 ? 0x6f86b0 : 0xd7e8ff);
    hemi.groundColor.set(night > 0.55 ? 0x243038 : 0x5a6458);
    fill.intensity = 0.42 + night * 0.18;
    fill.color.set(night > 0.55 ? 0x2a3a52 : 0x9aa7b4);
    const sky = new THREE.Color().lerpColors(new THREE.Color(0x8ec4e6), new THREE.Color(0x152238), night);
    scene.background = sky;
    fog.color.copy(sky);
    fog.near = 48;
    fog.far = 160;
    const neon = 0.55 + night * 1.15;
    for (const mat of neonMats) mat.emissiveIntensity = neon;
    const windows = 0.2 + night * 1.05;
    for (const mat of windowMats) mat.emissiveIntensity = windows;
  }
}

export function toneExposure(night: number): number {
  return clamp(1.05 + night * 0.12, 1, 1.25);
}
