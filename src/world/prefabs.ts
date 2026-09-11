import * as THREE from "three";

export function createHumanoid(opts: {
  body: number;
  accent: number;
  pants: number;
  watch?: boolean;
}): THREE.Group {
  const g = new THREE.Group();
  const bodyMat = new THREE.MeshStandardMaterial({ color: opts.body, roughness: 0.7 });
  const accentMat = new THREE.MeshStandardMaterial({
    color: opts.accent,
    emissive: opts.accent,
    emissiveIntensity: opts.watch ? 0.7 : 0.15,
    roughness: 0.45
  });
  const pantsMat = new THREE.MeshStandardMaterial({ color: opts.pants, roughness: 0.8 });
  const skin = new THREE.MeshStandardMaterial({ color: 0xc9a07a, roughness: 0.65 });

  const torso = new THREE.Mesh(new THREE.BoxGeometry(0.52, 0.62, 0.3), bodyMat);
  torso.position.y = 1.18;
  torso.castShadow = true;
  g.add(torso);

  const stripe = new THREE.Mesh(new THREE.BoxGeometry(0.54, 0.08, 0.32), accentMat);
  stripe.position.y = 1.28;
  g.add(stripe);

  const head = new THREE.Mesh(new THREE.BoxGeometry(0.28, 0.28, 0.28), skin);
  head.position.y = 1.64;
  g.add(head);

  const visor = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.08, 0.1), accentMat);
  visor.position.set(0, 1.66, 0.12);
  g.add(visor);

  for (const side of [-1, 1]) {
    const arm = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.5, 0.16), bodyMat);
    arm.position.set(0.34 * side, 1.12, 0);
    arm.castShadow = true;
    g.add(arm);
    const leg = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.62, 0.2), pantsMat);
    leg.position.set(0.12 * side, 0.5, 0);
    leg.castShadow = true;
    g.add(leg);
  }

  if (opts.watch) {
    const bar = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.08, 0.08), accentMat);
    bar.position.set(0, 1.42, 0.16);
    g.add(bar);
  }
  return g;
}

export type VehicleKind = "coupe" | "van" | "taxi" | "hauler" | "watch";

export function createVehicleMesh(kind: VehicleKind, paint: number, accent: number): THREE.Group {
  const g = new THREE.Group();
  const bodyMat = new THREE.MeshStandardMaterial({ color: paint, roughness: 0.38, metalness: 0.25 });
  const trim = new THREE.MeshStandardMaterial({
    color: accent,
    emissive: accent,
    emissiveIntensity: 0.55,
    roughness: 0.4
  });
  const dark = new THREE.MeshStandardMaterial({ color: 0x11151b, roughness: 0.5, metalness: 0.3 });
  const glass = new THREE.MeshStandardMaterial({
    color: 0x87d6ff,
    roughness: 0.15,
    metalness: 0.4,
    transparent: true,
    opacity: 0.45
  });

  const length = kind === "van" || kind === "hauler" ? 4.3 : 3.7;
  const width = kind === "hauler" ? 1.85 : 1.7;
  const height = kind === "van" ? 1.35 : 0.72;
  const body = new THREE.Mesh(new THREE.BoxGeometry(width, height, length), bodyMat);
  body.position.y = kind === "van" ? 0.95 : 0.62;
  body.castShadow = true;
  g.add(body);

  const cabinH = kind === "van" ? 0.55 : 0.62;
  const cabin = new THREE.Mesh(new THREE.BoxGeometry(width * 0.92, cabinH, length * 0.42), glass);
  cabin.position.set(0, body.position.y + height * 0.45, kind === "van" ? 0.35 : 0.45);
  g.add(cabin);

  for (const [x, z] of [
    [-width * 0.48, length * 0.32],
    [width * 0.48, length * 0.32],
    [-width * 0.48, -length * 0.32],
    [width * 0.48, -length * 0.32]
  ]) {
    const wheel = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.32, 0.22, 8), dark);
    wheel.rotation.z = Math.PI / 2;
    wheel.position.set(x, 0.32, z);
    g.add(wheel);
  }

  const lightGeo = new THREE.BoxGeometry(0.18, 0.1, 0.08);
  const fl = new THREE.Mesh(lightGeo, new THREE.MeshStandardMaterial({ color: 0xfff4c8, emissive: 0xfff1b0, emissiveIntensity: 0.8 }));
  const fr = fl.clone();
  fl.position.set(-width * 0.35, 0.55, length * 0.5);
  fr.position.set(width * 0.35, 0.55, length * 0.5);
  g.add(fl, fr);

  if (kind === "taxi") {
    const sign = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.16, 0.28), trim);
    sign.position.set(0, 1.28, 0.1);
    g.add(sign);
  }
  if (kind === "watch") {
    const bar = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.14, 0.28), trim);
    bar.position.set(0, 1.22, 0.1);
    g.add(bar);
    const stripe = new THREE.Mesh(new THREE.BoxGeometry(width + 0.02, 0.1, length * 0.7), trim);
    stripe.position.y = 0.72;
    g.add(stripe);
  }
  return g;
}

export function createTree(): THREE.Group {
  const g = new THREE.Group();
  const trunk = new THREE.Mesh(
    new THREE.CylinderGeometry(0.12, 0.16, 1.1, 5),
    new THREE.MeshStandardMaterial({ color: 0x4a3424, roughness: 1 })
  );
  trunk.position.y = 0.55;
  const leaf = new THREE.Mesh(
    new THREE.ConeGeometry(0.85, 1.6, 6),
    new THREE.MeshStandardMaterial({ color: 0x1f6a4a, roughness: 0.85 })
  );
  leaf.position.y = 1.7;
  g.add(trunk, leaf);
  return g;
}
