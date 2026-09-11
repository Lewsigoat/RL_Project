import type { LandmarkMap } from "../core/types";
import { CITY_HALF } from "../core/types";

export class Minimap {
  private readonly canvas = document.querySelector("#minimap") as HTMLCanvasElement;
  private readonly ctx = this.canvas.getContext("2d")!;

  draw(opts: {
    playerX: number;
    playerZ: number;
    yaw: number;
    roads: { x: number; z: number }[][];
    police: { x: number; z: number }[];
    marker: { x: number; z: number } | null;
    landmarks: LandmarkMap;
    showLandmarks: boolean;
  }): void {
    const { ctx, canvas } = this;
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "rgba(6, 12, 18, 0.92)";
    ctx.fillRect(0, 0, w, h);

    ctx.save();
    ctx.translate(w / 2, h / 2);
    ctx.rotate(-opts.yaw);
    const scale = 1.05;
    const sx = (x: number) => ((x - opts.playerX) / (CITY_HALF * 2)) * w * scale;
    const sz = (z: number) => ((z - opts.playerZ) / (CITY_HALF * 2)) * h * scale;

    ctx.strokeStyle = "rgba(94, 242, 227, 0.28)";
    ctx.lineWidth = 3;
    for (const line of opts.roads) {
      if (line.length < 2) continue;
      ctx.beginPath();
      ctx.moveTo(sx(line[0]!.x), sz(line[0]!.z));
      ctx.lineTo(sx(line[1]!.x), sz(line[1]!.z));
      ctx.stroke();
    }

    if (opts.showLandmarks) {
      ctx.fillStyle = "rgba(255, 200, 87, 0.7)";
      for (const p of [opts.landmarks.market, opts.landmarks.depot, opts.landmarks.safehouse]) {
        ctx.fillRect(sx(p.x) - 2, sz(p.z) - 2, 4, 4);
      }
    }

    ctx.fillStyle = "#ff4d9a";
    for (const p of opts.police) {
      ctx.beginPath();
      ctx.arc(sx(p.x), sz(p.z), 3.2, 0, Math.PI * 2);
      ctx.fill();
    }

    if (opts.marker) {
      ctx.fillStyle = "#ffc857";
      ctx.beginPath();
      ctx.arc(sx(opts.marker.x), sz(opts.marker.z), 5, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();

    ctx.fillStyle = "#5ef2e3";
    ctx.beginPath();
    ctx.moveTo(w / 2, h / 2 - 7);
    ctx.lineTo(w / 2 + 5, h / 2 + 6);
    ctx.lineTo(w / 2 - 5, h / 2 + 6);
    ctx.closePath();
    ctx.fill();

    ctx.strokeStyle = "rgba(94, 242, 227, 0.45)";
    ctx.strokeRect(1, 1, w - 2, h - 2);
  }
}
