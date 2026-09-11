import * as THREE from "three";
import { CITY_HALF, ROAD_COORDS, ROAD_WIDTH, SIDEWALK, type LandmarkMap } from "../core/types";
import { mulberry32, pick } from "../core/math";
import { CollisionWorld } from "./CollisionWorld";
import { createTree } from "./prefabs";

export interface ParkSpot {
  id: string;
  x: number;
  z: number;
  heading: number;
}

export interface CityData {
  group: THREE.Group;
  collision: CollisionWorld;
  landmarks: LandmarkMap;
  sidewalks: { x: number; z: number }[];
  roadPolylines: { x: number; z: number }[][];
  parked: ParkSpot[];
  trafficLoops: { x: number; z: number }[][];
  neonMats: THREE.MeshStandardMaterial[];
  windowMats: THREE.MeshStandardMaterial[];
  clouds: THREE.Mesh;
  water: THREE.Mesh;
  markers: THREE.Group;
}

const BUILD_COLORS = [0x1b2833, 0x24303a, 0x2a2434, 0x1d2a2c, 0x32242a, 0x253040];
const ACCENTS = [0x5ef2e3, 0xff4d9a, 0xffc857, 0x7cffb2, 0x7aa8ff, 0xff7ad1];

export function buildCity(scene: THREE.Scene): CityData {
  const rng = mulberry32(0x4e0c);
  const group = new THREE.Group();
  const collision = new CollisionWorld();
  const neonMats: THREE.MeshStandardMaterial[] = [];
  const windowMats: THREE.MeshStandardMaterial[] = [];
  const sidewalks: { x: number; z: number }[] = [];
  const markers = new THREE.Group();

  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(CITY_HALF * 2 + 20, CITY_HALF * 2 + 20),
    new THREE.MeshStandardMaterial({ color: 0x141a16, roughness: 0.95 })
  );
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  group.add(ground);

  addRoads(group, sidewalks);

  const landmarks: LandmarkMap = {
    plaza: { x: 0, z: 8 },
    market: { x: -58, z: -58 },
    depot: { x: 60, z: -58 },
    safehouse: { x: 58, z: 58 },
    canal: { x: -58, z: 58 }
  };

  addPlaza(group, collision, neonMats, windowMats);
  addMarket(group, collision, neonMats, windowMats, rng);
  addDepot(group, collision, neonMats, windowMats, rng);
  addPark(group, collision, neonMats);
  addCanal(group, collision, neonMats);
  fillLots(group, collision, neonMats, windowMats, sidewalks, rng);
  addStreetFurniture(group, neonMats, rng);
  addPerimeter(group, collision);

  const water = group.getObjectByName("canal-water") as THREE.Mesh;
  const clouds = makeClouds();
  group.add(clouds);
  group.add(markers);
  scene.add(group);

  const parked: ParkSpot[] = [
    { id: "ember-coupe", x: 8, z: -14, heading: 0.2 },
    { id: "volt-runner", x: -54, z: -62, heading: Math.PI * 0.5 },
    { id: "slate-hauler", x: 68, z: -48, heading: Math.PI },
    { id: "pearl-cruiser", x: 48, z: 50, heading: -0.4 },
    { id: "grid-taxi", x: -12, z: 22, heading: Math.PI * 0.5 }
  ];

  return {
    group,
    collision,
    landmarks,
    sidewalks,
    roadPolylines: roadLines(),
    parked,
    trafficLoops: trafficLoops(),
    neonMats,
    windowMats,
    clouds,
    water,
    markers
  };
}

function addRoads(group: THREE.Group, sidewalks: { x: number; z: number }[]): void {
  const asphalt = new THREE.MeshStandardMaterial({ color: 0x1a1f25, roughness: 0.42, metalness: 0.08 });
  const walk = new THREE.MeshStandardMaterial({ color: 0x2b3036, roughness: 0.85 });
  const paint = new THREE.MeshStandardMaterial({ color: 0xf4e3a1, roughness: 0.6, emissive: 0x2a2410, emissiveIntensity: 0.2 });
  const white = new THREE.MeshStandardMaterial({ color: 0xe8eef4, roughness: 0.5 });

  for (const c of ROAD_COORDS) {
    const ns = new THREE.Mesh(new THREE.BoxGeometry(ROAD_WIDTH, 0.05, CITY_HALF * 2), asphalt);
    ns.position.set(c, 0.02, 0);
    ns.receiveShadow = true;
    group.add(ns);
    const ew = new THREE.Mesh(new THREE.BoxGeometry(CITY_HALF * 2, 0.05, ROAD_WIDTH), asphalt);
    ew.position.set(0, 0.021, c);
    ew.receiveShadow = true;
    group.add(ew);

    for (const side of [-1, 1]) {
      const sw1 = new THREE.Mesh(new THREE.BoxGeometry(SIDEWALK, 0.08, CITY_HALF * 2), walk);
      sw1.position.set(c + side * (ROAD_WIDTH / 2 + SIDEWALK / 2), 0.04, 0);
      group.add(sw1);
      const sw2 = new THREE.Mesh(new THREE.BoxGeometry(CITY_HALF * 2, 0.08, SIDEWALK), walk);
      sw2.position.set(0, 0.041, c + side * (ROAD_WIDTH / 2 + SIDEWALK / 2));
      group.add(sw2);
    }
  }

  for (const x of ROAD_COORDS) {
    for (let z = -CITY_HALF + 8; z < CITY_HALF; z += 8) {
      const dash = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.04, 2.2), paint);
      dash.position.set(x, 0.05, z);
      group.add(dash);
    }
  }
  for (const z of ROAD_COORDS) {
    for (let x = -CITY_HALF + 8; x < CITY_HALF; x += 8) {
      const dash = new THREE.Mesh(new THREE.BoxGeometry(2.2, 0.04, 0.16), paint);
      dash.position.set(x, 0.05, z);
      group.add(dash);
    }
  }

  for (const x of ROAD_COORDS) {
    for (const z of ROAD_COORDS) {
      for (let i = 0; i < 5; i += 1) {
        const stripe = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.05, ROAD_WIDTH * 0.7), white);
        stripe.position.set(x - 2 + i * 1.0, 0.055, z);
        group.add(stripe);
      }
    }
  }

  for (const x of ROAD_COORDS) {
    for (const z of [-70, -50, -30, -10, 10, 30, 50, 70]) {
      sidewalks.push({ x: x + ROAD_WIDTH / 2 + 1.4, z });
      sidewalks.push({ x: x - ROAD_WIDTH / 2 - 1.4, z });
    }
  }
  for (const z of ROAD_COORDS) {
    for (const x of [-70, -50, -30, -10, 10, 30, 50, 70]) {
      sidewalks.push({ x, z: z + ROAD_WIDTH / 2 + 1.4 });
      sidewalks.push({ x, z: z - ROAD_WIDTH / 2 - 1.4 });
    }
  }
}

function addPlaza(
  group: THREE.Group,
  collision: CollisionWorld,
  neonMats: THREE.MeshStandardMaterial[],
  windowMats: THREE.MeshStandardMaterial[]
): void {
  const plaza = new THREE.Mesh(
    new THREE.CylinderGeometry(16, 16, 0.08, 24),
    new THREE.MeshStandardMaterial({ color: 0x2a3138, roughness: 0.7 })
  );
  plaza.position.set(0, 0.05, 0);
  group.add(plaza);

  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(9.5, 0.12, 8, 32),
    neonMat(0x5ef2e3, neonMats)
  );
  ring.rotation.x = Math.PI / 2;
  ring.position.y = 0.2;
  group.add(ring);

  const shaft = new THREE.Mesh(
    new THREE.BoxGeometry(4.2, 28, 4.2),
    new THREE.MeshStandardMaterial({ color: 0x1a222b, roughness: 0.5, metalness: 0.25 })
  );
  shaft.position.set(0, 14, 0);
  shaft.castShadow = true;
  group.add(shaft);
  collision.addBox(0, 0, 2.3, 2.3, 0, 28);

  const cap = new THREE.Mesh(new THREE.BoxGeometry(6.2, 2.2, 6.2), neonMat(0xff4d9a, neonMats));
  cap.position.set(0, 29, 0);
  group.add(cap);

  addSign(group, neonMats, 0, 8.2, 8.6, "VOLT SPIRE", 0x5ef2e3);
  addBuilding(group, collision, neonMats, windowMats, 18, 18, 7, 9, 14, 0x24313c, 0x7aa8ff);
  addBuilding(group, collision, neonMats, windowMats, -18, 16, 6, 7, 11, 0x2a2434, 0xff4d9a);
}

function addMarket(
  group: THREE.Group,
  collision: CollisionWorld,
  neonMats: THREE.MeshStandardMaterial[],
  windowMats: THREE.MeshStandardMaterial[],
  rng: () => number
): void {
  const pad = new THREE.Mesh(
    new THREE.BoxGeometry(26, 0.08, 26),
    new THREE.MeshStandardMaterial({ color: 0x2c2430, roughness: 0.8 })
  );
  pad.position.set(-58, 0.04, -58);
  group.add(pad);
  addSign(group, neonMats, -58, 5.4, -46, "MIDNIGHT MARKET", 0xff4d9a);

  for (let i = 0; i < 6; i += 1) {
    const stall = new THREE.Mesh(
      new THREE.BoxGeometry(3.2, 2.1, 2.4),
      new THREE.MeshStandardMaterial({ color: pick(rng, [0x6b2048, 0x204a55, 0x4a3b18]), roughness: 0.7 })
    );
    const x = -66 + (i % 3) * 7;
    const z = -66 + Math.floor(i / 3) * 8;
    stall.position.set(x, 1.05, z);
    stall.castShadow = true;
    group.add(stall);
    collision.addBox(x, z, 1.7, 1.3, 0, 2.2);
    const awning = new THREE.Mesh(new THREE.BoxGeometry(3.5, 0.12, 2.7), neonMat(pick(rng, ACCENTS), neonMats));
    awning.position.set(x, 2.2, z);
    group.add(awning);
  }
  addBuilding(group, collision, neonMats, windowMats, -70, -48, 5, 6, 8, 0x2a1f28, 0xffc857);
}

function addDepot(
  group: THREE.Group,
  collision: CollisionWorld,
  neonMats: THREE.MeshStandardMaterial[],
  windowMats: THREE.MeshStandardMaterial[],
  rng: () => number
): void {
  const yard = new THREE.Mesh(
    new THREE.BoxGeometry(28, 0.07, 24),
    new THREE.MeshStandardMaterial({ color: 0x2a2c28, roughness: 0.9 })
  );
  yard.position.set(60, 0.035, -58);
  group.add(yard);
  addSign(group, neonMats, 60, 6.2, -46, "CYAN RAIL DEPOT", 0x5ef2e3);

  for (const [x, z, w, d, h] of [
    [70, -66, 6, 8, 6],
    [52, -68, 7, 5, 5],
    [72, -52, 5, 10, 7]
  ] as const) {
    addBuilding(group, collision, neonMats, windowMats, x, z, w, d, h, 0x2a3030, 0x5ef2e3);
  }
  const crateMat = new THREE.MeshStandardMaterial({ color: 0x3d4a52, roughness: 0.8 });
  for (let i = 0; i < 5; i += 1) {
    const crate = new THREE.Mesh(new THREE.BoxGeometry(1.4, 1.2, 1.4), crateMat);
    crate.position.set(56 + rng() * 8, 0.6, -54 + rng() * 6);
    crate.castShadow = true;
    group.add(crate);
    collision.addBox(crate.position.x, crate.position.z, 0.75, 0.75, 0, 1.3);
  }
}

function addPark(group: THREE.Group, collision: CollisionWorld, neonMats: THREE.MeshStandardMaterial[]): void {
  const grass = new THREE.Mesh(
    new THREE.BoxGeometry(28, 0.08, 28),
    new THREE.MeshStandardMaterial({ color: 0x1c4a32, roughness: 1 })
  );
  grass.position.set(58, 0.03, 58);
  group.add(grass);
  addSign(group, neonMats, 58, 4.6, 45, "HARBOR LIGHTS", 0x7cffb2);

  const fountain = new THREE.Mesh(
    new THREE.CylinderGeometry(3.2, 3.6, 0.5, 12),
    new THREE.MeshStandardMaterial({ color: 0x8fd4ff, roughness: 0.2, metalness: 0.3, transparent: true, opacity: 0.75 })
  );
  fountain.position.set(58, 0.3, 58);
  group.add(fountain);
  collision.addBox(58, 58, 2.4, 2.4, 0, 1.2);

  const safe = new THREE.Mesh(
    new THREE.BoxGeometry(6, 3.2, 5),
    new THREE.MeshStandardMaterial({ color: 0x1d2a28, roughness: 0.6 })
  );
  safe.position.set(66, 1.6, 66);
  safe.castShadow = true;
  group.add(safe);
  collision.addBox(66, 66, 3.1, 2.6, 0, 3.3);
  addSign(group, neonMats, 66, 3.6, 63.2, "SAFEHOUSE", 0xffc857);

  for (const [x, z] of [
    [48, 48],
    [68, 48],
    [48, 68],
    [52, 62],
    [64, 50],
    [70, 60]
  ]) {
    const tree = createTree();
    tree.position.set(x, 0, z);
    group.add(tree);
    collision.addBox(x, z, 0.4, 0.4, 0, 2);
  }
}

function addCanal(group: THREE.Group, collision: CollisionWorld, neonMats: THREE.MeshStandardMaterial[]): void {
  const water = new THREE.Mesh(
    new THREE.BoxGeometry(22, 0.2, 26),
    new THREE.MeshStandardMaterial({
      color: 0x146a68,
      roughness: 0.15,
      metalness: 0.35,
      emissive: 0x063230,
      emissiveIntensity: 0.4
    })
  );
  water.name = "canal-water";
  water.position.set(-60, -0.02, 58);
  group.add(water);
  collision.addBox(-60, 58, 10.6, 12.6, -1, 0.4);
  addSign(group, neonMats, -60, 5, 44, "JADE CANAL", 0x7cffb2);

  const bridge = new THREE.Mesh(
    new THREE.BoxGeometry(6, 0.35, 8),
    new THREE.MeshStandardMaterial({ color: 0x3a4046, roughness: 0.55 })
  );
  bridge.position.set(-60, 0.35, 58);
  group.add(bridge);

  const pagoda = new THREE.Mesh(
    new THREE.BoxGeometry(5, 7, 5),
    new THREE.MeshStandardMaterial({ color: 0x2a1c22, roughness: 0.6 })
  );
  pagoda.position.set(-74, 3.5, 70);
  pagoda.castShadow = true;
  group.add(pagoda);
  collision.addBox(-74, 70, 2.6, 2.6, 0, 7);
  const roof = new THREE.Mesh(new THREE.ConeGeometry(4.2, 2.2, 4), neonMat(0xff4d9a, neonMats));
  roof.position.set(-74, 8.2, 70);
  roof.rotation.y = Math.PI / 4;
  group.add(roof);
}

function fillLots(
  group: THREE.Group,
  collision: CollisionWorld,
  neonMats: THREE.MeshStandardMaterial[],
  windowMats: THREE.MeshStandardMaterial[],
  sidewalks: { x: number; z: number }[],
  rng: () => number
): void {
  const roads = ROAD_COORDS;
  for (let i = 0; i < roads.length - 1; i += 1) {
    for (let j = 0; j < roads.length - 1; j += 1) {
      const x0 = roads[i]! + ROAD_WIDTH / 2 + SIDEWALK + 1.2;
      const x1 = roads[i + 1]! - ROAD_WIDTH / 2 - SIDEWALK - 1.2;
      const z0 = roads[j]! + ROAD_WIDTH / 2 + SIDEWALK + 1.2;
      const z1 = roads[j + 1]! - ROAD_WIDTH / 2 - SIDEWALK - 1.2;
      const cx = (x0 + x1) / 2;
      const cz = (z0 + z1) / 2;
      if (Math.hypot(cx, cz) < 22) continue;
      if (cx < -40 && cz < -40) continue;
      if (cx > 40 && cz < -40) continue;
      if (cx > 40 && cz > 40) continue;
      if (cx < -40 && cz > 40) continue;

      const lotW = x1 - x0;
      const lotD = z1 - z0;
      const alley = rng() > 0.45;
      if (alley) {
        const w = lotW * 0.38;
        const d = lotD * 0.78;
        const h1 = 8 + rng() * 16;
        const h2 = 7 + rng() * 14;
        const left = x0 + w * 0.55;
        const right = x1 - w * 0.55;
        addBuilding(group, collision, neonMats, windowMats, left, cz, w, d, h1, pick(rng, BUILD_COLORS), pick(rng, ACCENTS));
        addBuilding(group, collision, neonMats, windowMats, right, cz, w, d, h2, pick(rng, BUILD_COLORS), pick(rng, ACCENTS));
        sidewalks.push({ x: cx, z: cz });
      } else {
        const w = lotW * (0.62 + rng() * 0.2);
        const d = lotD * (0.62 + rng() * 0.2);
        addBuilding(
          group,
          collision,
          neonMats,
          windowMats,
          cx,
          cz,
          w,
          d,
          7 + rng() * 18,
          pick(rng, BUILD_COLORS),
          pick(rng, ACCENTS)
        );
      }
    }
  }
}

function addBuilding(
  group: THREE.Group,
  collision: CollisionWorld,
  neonMats: THREE.MeshStandardMaterial[],
  windowMats: THREE.MeshStandardMaterial[],
  x: number,
  z: number,
  w: number,
  d: number,
  h: number,
  color: number,
  accent: number
): void {
  const facade = new THREE.MeshStandardMaterial({ color, roughness: 0.72, metalness: 0.08 });
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), facade);
  mesh.position.set(x, h / 2, z);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  group.add(mesh);
  collision.addBox(x, z, w / 2, d / 2, 0, h);

  const win = windowMat(accent, windowMats);
  const inset = new THREE.Mesh(new THREE.BoxGeometry(w * 0.82, h * 0.72, 0.08), win);
  inset.position.set(x, h * 0.52, z + d / 2 + 0.05);
  group.add(inset);
  const inset2 = inset.clone();
  inset2.position.z = z - d / 2 - 0.05;
  group.add(inset2);

  if (h > 10) {
    const band = new THREE.Mesh(new THREE.BoxGeometry(w + 0.2, 0.35, d + 0.2), neonMat(accent, neonMats));
    band.position.set(x, h * 0.72, z);
    group.add(band);
  }
  if (h > 14) {
    const ac = new THREE.Mesh(
      new THREE.BoxGeometry(1.4, 0.8, 1.6),
      new THREE.MeshStandardMaterial({ color: 0x3a4248, roughness: 0.7 })
    );
    ac.position.set(x + w * 0.2, h + 0.4, z);
    group.add(ac);
  }
}

function addStreetFurniture(group: THREE.Group, neonMats: THREE.MeshStandardMaterial[], rng: () => number): void {
  const poleMat = new THREE.MeshStandardMaterial({ color: 0x22282e, roughness: 0.6 });
  const bulb = neonMat(0xffc857, neonMats);
  for (const c of ROAD_COORDS) {
    for (let t = -84; t <= 84; t += 20) {
      for (const side of [-1, 1]) {
        const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.1, 5.2, 5), poleMat);
        pole.position.set(c + side * 6.4, 2.6, t);
        group.add(pole);
        const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.22, 6, 6), bulb);
        lamp.position.set(c + side * 6.4, 5.15, t);
        group.add(lamp);
      }
    }
  }

  const names = ["VOLT MART", "JADE NOODLE", "GRID RADIO", "HARBOR WATCH", "CYAN PARTS", "NIGHT SHIFT"];
  let n = 0;
  for (const x of [-20, 20, -60, 60]) {
    for (const z of [-20, 20]) {
      addSign(group, neonMats, x, 6.8 + rng(), z + 10, names[n % names.length]!, pick(rng, ACCENTS));
      n += 1;
    }
  }
}

function addPerimeter(group: THREE.Group, collision: CollisionWorld): void {
  const wallMat = new THREE.MeshStandardMaterial({ color: 0x161b20, roughness: 0.9 });
  const h = 6;
  const t = 2;
  const span = CITY_HALF * 2 + 8;
  const north = new THREE.Mesh(new THREE.BoxGeometry(span, h, t), wallMat);
  north.position.set(0, h / 2, CITY_HALF + 2);
  const south = north.clone();
  south.position.z = -CITY_HALF - 2;
  const east = new THREE.Mesh(new THREE.BoxGeometry(t, h, span), wallMat);
  east.position.set(CITY_HALF + 2, h / 2, 0);
  const west = east.clone();
  west.position.x = -CITY_HALF - 2;
  group.add(north, south, east, west);
  collision.addBox(0, CITY_HALF + 2, span / 2, t / 2, 0, h);
  collision.addBox(0, -CITY_HALF - 2, span / 2, t / 2, 0, h);
  collision.addBox(CITY_HALF + 2, 0, t / 2, span / 2, 0, h);
  collision.addBox(-CITY_HALF - 2, 0, t / 2, span / 2, 0, h);
}

function addSign(
  group: THREE.Group,
  neonMats: THREE.MeshStandardMaterial[],
  x: number,
  y: number,
  z: number,
  text: string,
  color: number
): void {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 128;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#071018";
  ctx.fillRect(0, 0, 512, 128);
  ctx.strokeStyle = `#${color.toString(16).padStart(6, "0")}`;
  ctx.lineWidth = 8;
  ctx.strokeRect(8, 8, 496, 112);
  ctx.fillStyle = `#${color.toString(16).padStart(6, "0")}`;
  ctx.font = "bold 48px Trebuchet MS, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 256, 64);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  const mat = new THREE.MeshStandardMaterial({
    map: tex,
    emissive: color,
    emissiveIntensity: 0.55,
    emissiveMap: tex,
    roughness: 0.4
  });
  neonMats.push(mat);
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(7.2, 1.8), mat);
  mesh.position.set(x, y, z);
  group.add(mesh);
  const back = mesh.clone();
  back.rotation.y = Math.PI;
  group.add(back);
}

function neonMat(color: number, bag: THREE.MeshStandardMaterial[]): THREE.MeshStandardMaterial {
  const mat = new THREE.MeshStandardMaterial({
    color,
    emissive: color,
    emissiveIntensity: 0.9,
    roughness: 0.35,
    metalness: 0.15
  });
  bag.push(mat);
  return mat;
}

function windowMat(color: number, bag: THREE.MeshStandardMaterial[]): THREE.MeshStandardMaterial {
  const mat = new THREE.MeshStandardMaterial({
    color: 0x102028,
    emissive: color,
    emissiveIntensity: 0.35,
    roughness: 0.25,
    metalness: 0.2
  });
  bag.push(mat);
  return mat;
}

function makeClouds(): THREE.Mesh {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "rgba(0,0,0,0)";
  ctx.fillRect(0, 0, 256, 256);
  ctx.fillStyle = "rgba(220,230,240,0.28)";
  for (let i = 0; i < 18; i += 1) {
    ctx.beginPath();
    ctx.ellipse(40 + ((i * 47) % 200), 40 + ((i * 29) % 180), 36, 16, 0, 0, Math.PI * 2);
    ctx.fill();
  }
  const tex = new THREE.CanvasTexture(canvas);
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(220, 220), mat);
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.y = 46;
  mesh.name = "clouds";
  return mesh;
}

function roadLines(): { x: number; z: number }[][] {
  return ROAD_COORDS.flatMap((c) => [
    [
      { x: c, z: -CITY_HALF },
      { x: c, z: CITY_HALF }
    ],
    [
      { x: -CITY_HALF, z: c },
      { x: CITY_HALF, z: c }
    ]
  ]);
}

function trafficLoops(): { x: number; z: number }[][] {
  const off = 2.7;
  const outer = [
    { x: -80 + off, z: -80 + off },
    { x: 80 + off, z: -80 + off },
    { x: 80 + off, z: 80 + off },
    { x: -80 + off, z: 80 + off }
  ];
  const inner = [
    { x: -40 - off, z: -40 - off },
    { x: -40 - off, z: 40 - off },
    { x: 40 - off, z: 40 - off },
    { x: 40 - off, z: -40 - off }
  ];
  const crossNS = [
    { x: 0 + off, z: -80 },
    { x: 0 + off, z: 80 },
    { x: 0 - off, z: 80 },
    { x: 0 - off, z: -80 }
  ];
  const crossEW = [
    { x: -80, z: 0 - off },
    { x: 80, z: 0 - off },
    { x: 80, z: 0 + off },
    { x: -80, z: 0 + off }
  ];
  const mid = [
    { x: -80 + off, z: 40 + off },
    { x: 80 + off, z: 40 + off },
    { x: 80 + off, z: -40 + off },
    { x: -80 + off, z: -40 + off }
  ];
  return [outer, inner, crossNS, crossEW, mid, [...outer].reverse()];
}

export function createWorldMarker(color: number): THREE.Group {
  const g = new THREE.Group();
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(1.6, 0.08, 8, 24),
    new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 1.1 })
  );
  ring.rotation.x = Math.PI / 2;
  const beam = new THREE.Mesh(
    new THREE.CylinderGeometry(0.08, 0.08, 10, 6),
    new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      emissiveIntensity: 0.8,
      transparent: true,
      opacity: 0.55
    })
  );
  beam.position.y = 5;
  g.add(ring, beam);
  return g;
}
