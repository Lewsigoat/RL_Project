import * as THREE from "three";
import { AudioEngine } from "../audio/AudioEngine";
import { GameCamera } from "../camera/GameCamera";
import { CombatSystem } from "../combat/CombatSystem";
import { Input } from "../input/Input";
import { MissionDirector } from "../missions/MissionDirector";
import { Pedestrian, randomPedColors } from "../npcs/Pedestrian";
import { PoliceDirector } from "../npcs/PoliceDirector";
import { loadSave, mergeSave } from "../persist/SaveStore";
import { Player } from "../player/Player";
import { DayNight, toneExposure } from "../time/DayNight";
import { Hud } from "../ui/Hud";
import { Minimap } from "../ui/Minimap";
import { Screens } from "../ui/Screens";
import { Vehicle } from "../vehicles/Vehicle";
import { WantedSystem } from "../wanted/WantedSystem";
import { buildCity, createWorldMarker, type CityData } from "../world/City";
import { circlesOverlap, separateCircles } from "../world/CollisionWorld";
import type { FailReason, GamePhase, SaveData } from "./types";
import { MISSION_VEHICLE_ID } from "./types";

export class Game {
  readonly renderer: THREE.WebGLRenderer;
  readonly scene = new THREE.Scene();
  readonly camera: THREE.PerspectiveCamera;
  readonly input = new Input();
  readonly player = new Player();
  readonly follow = new GameCamera();
  readonly wanted = new WantedSystem();
  readonly mission = new MissionDirector();
  readonly dayNight = new DayNight();
  readonly audio = new AudioEngine();
  readonly hud = new Hud();
  readonly minimap = new Minimap();
  readonly police = new PoliceDirector();
  readonly vehicles: Vehicle[] = [];
  readonly peds: Pedestrian[] = [];
  readonly clock = new THREE.Clock();
  readonly combat: CombatSystem;
  readonly screens: Screens;
  city!: CityData;
  save: SaveData;
  phase: GamePhase = "title";
  private sun!: THREE.DirectionalLight;
  private hemi!: THREE.HemisphereLight;
  private fill!: THREE.AmbientLight;
  private fog!: THREE.Fog;
  private marker!: THREE.Group;
  private occupied: Vehicle | null = null;
  private nearby: Vehicle | null = null;
  private elapsed = 0;
  private canvas: HTMLCanvasElement;
  private nav: { x: number; z: number; sprint: boolean } | null = null;
  private navRoute: { x: number; z: number }[] = [];
  private stuck = 0;
  private reversing = 0;

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas;
    this.save = loadSave();
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.camera = new THREE.PerspectiveCamera(62, window.innerWidth / window.innerHeight, 0.1, 220);
    this.combat = new CombatSystem(this.scene);
    this.screens = new Screens({
      onStart: () => this.begin(false),
      onContinue: () => this.begin(true),
      onOnboardNext: () => this.advanceOnboard(),
      onResume: () => this.resume(),
      onRestart: () => this.begin(false),
      onTitle: () => this.toTitle(),
      onRoam: () => this.roam(),
      onSens: (v) => {
        this.save = mergeSave(this.save, { mouseSensitivity: v });
      },
      onVol: (v) => {
        this.save = mergeSave(this.save, { volume: v });
        this.audio.setVolume(v);
      }
    });
    this.screens.setContinueEnabled(this.save.missionCompleted);
    this.screens.setSliders(this.save.mouseSensitivity, this.save.volume);
    this.audio.setVolume(this.save.volume);
    this.input.attach(canvas);
    this.buildScene();
    window.addEventListener("resize", this.onResize);
    canvas.addEventListener("click", this.onCanvasClick);
    document.addEventListener("pointerlockchange", this.onPointerLock);
  }

  start(): void {
    this.screens.apply(this.phase);
    this.hud.setVisible(false);
    this.tick();
  }

  snapshot(): {
    phase: GamePhase;
    health: number;
    wanted: number;
    money: number;
    x: number;
    z: number;
    inVehicle: boolean;
    vehicleId: string | null;
    mission: string;
    objective: string;
    kmh: number;
    clock: string;
    navigating: boolean;
  } {
    return {
      phase: this.phase,
      health: this.player.health,
      wanted: this.wanted.level,
      money: this.save.money,
      x: this.player.x,
      z: this.player.z,
      inVehicle: this.player.inVehicle,
      vehicleId: this.occupied?.id ?? null,
      mission: this.mission.stage,
      objective: this.mission.objectiveText(),
      kmh: this.occupied?.kmh() ?? 0,
      clock: this.dayNight.label(),
      navigating: Boolean(this.nav)
    };
  }

  lookToward(x: number, z: number): void {
    this.follow.yaw = Math.atan2(x - this.player.x, z - this.player.z);
  }

  queueFire(): void {
    this.input.queueFire();
  }

  setNav(x: number, z: number, sprint = true): void {
    const straight = Math.hypot(this.player.x - x, this.player.z - z) < 18;
    this.navRoute = straight ? [] : roadRoute(this.player.x, this.player.z, x, z);
    const first = this.navRoute.shift() ?? { x, z };
    this.nav = { ...first, sprint };
    this.stuck = 0;
    this.reversing = 0;
  }

  clearNav(): void {
    this.nav = null;
    this.navRoute = [];
    this.input.keys.delete("KeyW");
    this.input.keys.delete("KeyS");
    this.input.keys.delete("ShiftLeft");
  }

  interactNow(): void {
    this.tryInteract();
  }

  private buildScene(): void {
    this.fog = new THREE.Fog(0x152238, 48, 160);
    this.scene.fog = this.fog;
    this.scene.background = new THREE.Color(0x24364c);
    this.hemi = new THREE.HemisphereLight(0xc5d8f0, 0x2a3030, 0.95);
    this.scene.add(this.hemi);
    this.fill = new THREE.AmbientLight(0x6a7c90, 0.5);
    this.scene.add(this.fill);
    this.sun = new THREE.DirectionalLight(0xffe6c4, 1.6);
    this.sun.position.set(40, 50, 18);
    this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(1024, 1024);
    this.sun.shadow.camera.near = 4;
    this.sun.shadow.camera.far = 140;
    this.sun.shadow.camera.left = -70;
    this.sun.shadow.camera.right = 70;
    this.sun.shadow.camera.top = 70;
    this.sun.shadow.camera.bottom = -70;
    this.scene.add(this.sun);
    this.city = buildCity(this.scene);
    this.scene.add(this.player.group);
    this.scene.add(this.police.group);
    this.marker = createWorldMarker(0xffc857);
    this.city.markers.add(this.marker);

    const paints: Record<string, { kind: Vehicle["kind"]; paint: number; accent: number }> = {
      "ember-coupe": { kind: "coupe", paint: 0xc45a22, accent: 0xffc857 },
      "volt-runner": { kind: "van", paint: 0x14c4b8, accent: 0x5ef2e3 },
      "slate-hauler": { kind: "hauler", paint: 0x2a3138, accent: 0x7aa8ff },
      "pearl-cruiser": { kind: "coupe", paint: 0xd6dce4, accent: 0xff4d9a },
      "grid-taxi": { kind: "taxi", paint: 0xffc857, accent: 0xff4d9a }
    };
    for (const spot of this.city.parked) {
      const spec = paints[spot.id] ?? { kind: "coupe" as const, paint: 0x44555c, accent: 0x5ef2e3 };
      const car = new Vehicle(spot.id, spec.kind, spot.x, spot.z, spot.heading, spec.paint, spec.accent);
      this.vehicles.push(car);
      this.scene.add(car.group);
    }
    const trafficPaints = [0x355066, 0x6a2a40, 0x2d4a38, 0x3c3c48, 0x704820, 0x1f3a44];
    this.city.trafficLoops.forEach((loop, i) => {
      const p = loop[i % loop.length]!;
      const car = new Vehicle(
        `traffic-${i}`,
        i % 2 === 0 ? "coupe" : "taxi",
        p.x,
        p.z,
        0,
        trafficPaints[i % trafficPaints.length]!,
        0x5ef2e3
      );
      car.assignLoop(loop, i);
      this.vehicles.push(car);
      this.scene.add(car.group);
    });

    for (let i = 0; i < 12; i += 1) {
      const spot = this.city.sidewalks[i * 3] ?? this.city.sidewalks[i]!;
      const colors = randomPedColors();
      const ped = new Pedestrian(spot.x, spot.z, colors.body, colors.accent);
      this.peds.push(ped);
      this.scene.add(ped.group);
    }
  }

  private begin(continueSave: boolean): void {
    this.audio.unlock();
    this.audio.blip();
    this.resetActors();
    if (continueSave && this.save.missionCompleted) {
      this.mission.skipToRoam();
      this.enterPlaying();
    } else {
      this.mission.reset();
      this.phase = "onboarding";
      this.screens.step = 0;
      this.screens.showOnboard();
      this.screens.apply(this.phase);
      this.hud.setVisible(false);
      this.exitLock();
    }
  }

  private advanceOnboard(): void {
    this.audio.blip(640, 0.06);
    if (this.screens.nextOnboard()) this.enterPlaying();
  }

  private enterPlaying(): void {
    this.phase = "playing";
    this.screens.apply(this.phase);
    this.hud.setVisible(true);
  }

  private resume(): void {
    if (this.phase !== "paused") return;
    this.audio.blip();
    this.enterPlaying();
  }

  private roam(): void {
    this.audio.success();
    this.phase = "playing";
    this.screens.apply(this.phase);
    this.hud.setVisible(true);
  }

  private toTitle(): void {
    this.exitLock();
    this.save = mergeSave(this.save, {
      money: this.save.money,
      bestWanted: this.save.bestWanted
    });
    this.phase = "title";
    this.screens.setContinueEnabled(this.save.missionCompleted);
    this.screens.apply(this.phase);
    this.hud.setVisible(false);
  }

  private fail(reason: FailReason): void {
    this.phase = "failed";
    this.screens.setFail(reason);
    this.screens.apply(this.phase);
    this.hud.setVisible(true);
    this.exitLock();
    this.audio.sting();
  }

  private complete(reward: number): void {
    this.save = mergeSave(this.save, {
      money: this.save.money + reward,
      missionCompleted: true,
      bestWanted: Math.max(this.save.bestWanted, this.wanted.level)
    });
    this.phase = "complete";
    this.screens.setComplete(reward);
    this.screens.setContinueEnabled(true);
    this.screens.apply(this.phase);
    this.exitLock();
    this.audio.success();
  }

  private resetActors(): void {
    this.player.reset();
    this.wanted.reset();
    this.occupied = null;
    this.clearNav();
    this.follow.yaw = 0.2;
    this.follow.pitch = 0.35;
    for (const v of this.vehicles) {
      if (v.id.startsWith("traffic-")) v.resetTraffic();
      else v.resetPark();
      v.group.visible = true;
    }
    this.city.sidewalks.forEach((spot, i) => {
      const ped = this.peds[i];
      if (ped) ped.reset(spot.x, spot.z);
    });
    this.police.reset();
  }

  private tick = (): void => {
    requestAnimationFrame(this.tick);
    const dt = Math.min(0.033, this.clock.getDelta());
    this.elapsed += dt;
    this.handlePhaseInput();
    if (this.phase === "playing") this.updatePlay(dt);
    else this.updateIdleCamera(dt);
    this.dayNight.apply(this.sun, this.hemi, this.fill, this.scene, this.fog, this.city.neonMats, this.city.windowMats);
    this.renderer.toneMappingExposure = toneExposure(this.dayNight.nightFactor);
    this.city.clouds.position.x = Math.sin(this.elapsed * 0.03) * 16;
    this.city.clouds.position.z = Math.cos(this.elapsed * 0.02) * 10;
    const waterMat = this.city.water.material as THREE.MeshStandardMaterial;
    waterMat.emissiveIntensity = 0.28 + Math.sin(this.elapsed * 1.4) * 0.1;
    this.renderer.render(this.scene, this.camera);
  };

  private handlePhaseInput(): void {
    if (!this.input.consumePause()) return;
    if (this.phase === "playing") {
      this.phase = "paused";
      this.screens.apply(this.phase);
      this.exitLock();
      this.audio.blip(280, 0.07);
    } else if (this.phase === "paused") {
      this.resume();
    } else if (this.phase === "onboarding") {
      this.enterPlaying();
    }
  }

  private updateIdleCamera(dt: number): void {
    this.follow.applyLook(6 * dt, 0, 0.15);
    this.follow.update(dt, this.camera, this.player, this.occupied);
  }

  private updatePlay(dt: number): void {
    const look = this.input.consumeMouse();
    this.follow.applyLook(look.x, look.y, this.save.mouseSensitivity);
    const keyLook = this.input.lookKeys();
    this.follow.yaw -= keyLook.x * 1.7 * dt * this.save.mouseSensitivity;
    this.follow.pitch = Math.min(1.15, Math.max(0.08, this.follow.pitch + keyLook.y * 1.1 * dt * this.save.mouseSensitivity));
    this.dayNight.update(dt);
    this.combat.update(dt);
    this.tickNav(dt);

    if (this.input.consumeInteract()) this.tryInteract();

    const allCars = [...this.vehicles, ...this.police.cars];
    if (this.occupied) {
      this.occupied.updateDriven(dt, this.input, this.city.collision, allCars, this.follow.yaw);
      this.player.setPosition(this.occupied.x, this.occupied.z, this.occupied.heading);
      this.player.inVehicle = true;
    } else {
      this.player.inVehicle = false;
      this.player.update(dt, this.input, this.follow.yaw, this.city.collision);
      this.unstickFromCars(allCars);
    }

    this.nearby = this.findNearbyVehicle();
    for (const car of this.vehicles) {
      if (car === this.occupied) continue;
      if (car.traffic && !car.occupied) {
        car.updateTraffic(
          dt,
          this.city.collision,
          allCars,
          this.player.x,
          this.player.z,
          this.player.inVehicle ? 1.8 : this.player.radius
        );
      }
    }

    const threatSpeed = this.occupied ? Math.abs(this.occupied.speed) : Math.hypot(this.player.vx, this.player.vz);
    for (const ped of this.peds) {
      ped.update(dt, this.city.collision, this.city.sidewalks, this.player.x, this.player.z, threatSpeed);
      if (!ped.down && this.occupied && Math.abs(this.occupied.speed) > 7) {
        if (circlesOverlap(this.occupied.x, this.occupied.z, this.occupied.radius * 0.7, ped.x, ped.z, ped.radius)) {
          ped.hit(50);
          this.wanted.report("vehicular", this.player.x, this.player.z);
          this.audio.sting();
        }
      }
    }

    if (this.input.consumeFire()) {
      const dir = new THREE.Vector3();
      this.camera.getWorldDirection(dir);
      const origin = this.camera.position.clone().add(dir.clone().multiplyScalar(0.6));
      origin.y = this.player.inVehicle ? 1.2 : 1.45;
      this.combat.tryFire({
        origin,
        dir,
        player: this.player,
        peds: this.peds,
        police: this.police,
        vehicles: allCars,
        collision: this.city.collision,
        wanted: this.wanted
      });
      this.audio.gunshot();
      for (const ped of this.peds) {
        if (Math.hypot(ped.x - this.player.x, ped.z - this.player.z) < 32) ped.scare(this.player.x, this.player.z);
      }
    }

    const police = this.police.update({
      dt,
      wanted: this.wanted.level,
      playerX: this.player.x,
      playerZ: this.player.z,
      playerSpeed: threatSpeed,
      onFoot: !this.player.inVehicle,
      lastKnown: this.wanted.lastKnown,
      collision: this.city.collision,
      vehicles: allCars
    });
    if (police.seen) this.wanted.markSeen(this.player.x, this.player.z);
    for (const shot of police.shots) {
      if (this.city.collision.losClear(shot.x, shot.z, this.player.x, this.player.z)) {
        this.player.damage(4 + this.wanted.level * 0.6);
        this.hud.pulseDamage(this.elapsed);
      }
    }
    if (this.occupied) {
      for (const watch of this.police.cars) {
        if (!watch.group.visible) continue;
        if (
          circlesOverlap(this.occupied.x, this.occupied.z, this.occupied.radius, watch.x, watch.z, watch.radius) &&
          Math.abs(this.occupied.speed) > 8
        ) {
          this.wanted.report("ramWatch", this.player.x, this.player.z);
        }
      }
    }
    const nearestCop = Math.min(
      ...this.police.feet.filter((f) => f.group.visible && !f.down).map((f) => Math.hypot(f.x - this.player.x, f.z - this.player.z)),
      ...this.police.cars.filter((c) => c.group.visible).map((c) => Math.hypot(c.x - this.player.x, c.z - this.player.z)),
      999
    );
    this.wanted.update(dt, police.seen, this.player.x, this.player.z, nearestCop, threatSpeed);
    this.save.bestWanted = Math.max(this.save.bestWanted, this.wanted.level);

    const mission = this.mission.update(
      {
        playerX: this.player.x,
        playerZ: this.player.z,
        inVehicle: this.player.inVehicle,
        vehicleId: this.occupied?.id ?? null,
        wantedLevel: this.wanted.level
      },
      this.city.landmarks
    );
    if (mission.raiseWanted) {
      this.wanted.setAtLeast(mission.raiseWanted, this.player.x, this.player.z);
      this.audio.sting();
    }
    if (mission.justCompleted && mission.reward) this.complete(mission.reward);

    if (mission.marker) {
      this.marker.visible = true;
      this.marker.position.set(mission.marker.x, 0.15, mission.marker.z);
      this.marker.rotation.y += dt;
    } else {
      this.marker.visible = false;
    }

    this.follow.update(dt, this.camera, this.player, this.occupied);
    this.audio.update(dt, Boolean(this.occupied), Math.abs(this.occupied?.speed ?? 0), this.wanted.level);

    if (this.player.health <= 0) this.fail("downed");
    else if (police.arresting) this.fail("arrested");

    const prompt = this.promptText(police.arresting);
    this.hud.update({
      now: this.elapsed,
      health: this.player.health,
      wanted: this.wanted.level,
      money: this.save.money,
      objective: mission.objective,
      prompt,
      driving: Boolean(this.occupied),
      kmh: this.occupied?.kmh() ?? 0,
      clock: this.dayNight.label(),
      showLookHint: !this.input.pointerLocked && !this.input.lookHeld
    });
    this.minimap.draw({
      playerX: this.player.x,
      playerZ: this.player.z,
      yaw: this.follow.yaw,
      roads: this.city.roadPolylines,
      police: [
        ...this.police.feet.filter((f) => f.group.visible && !f.down).map((f) => ({ x: f.x, z: f.z })),
        ...this.police.cars.filter((c) => c.group.visible).map((c) => ({ x: c.x, z: c.z }))
      ],
      marker: mission.marker,
      landmarks: this.city.landmarks,
      showLandmarks: true
    });
  }

  private tickNav(dt: number): void {
    if (!this.nav) return;
    const dist = Math.hypot(this.player.x - this.nav.x, this.player.z - this.nav.z);
    const last = this.navRoute.length === 0;
    const arrive = last ? (this.occupied ? 14 : 3.4) : 8;
    if (dist < arrive) {
      const next = this.navRoute.shift();
      if (!next) {
        this.clearNav();
        return;
      }
      this.nav = { ...next, sprint: this.nav.sprint };
      this.stuck = 0;
      return;
    }
    this.lookToward(this.nav.x, this.nav.z);
    if (this.reversing > 0) {
      this.reversing -= dt;
      this.input.keys.add("KeyS");
      this.input.keys.delete("KeyW");
      return;
    }
    this.input.keys.delete("KeyS");
    this.input.keys.add("KeyW");
    if (this.nav.sprint && !this.occupied) this.input.keys.add("ShiftLeft");
    const speed = this.occupied ? Math.abs(this.occupied.speed) : Math.hypot(this.player.vx, this.player.vz);
    if (speed < 1.2) this.stuck += dt;
    else this.stuck = 0;
    if (this.stuck > 0.7) {
      this.reversing = 0.55;
      this.stuck = 0;
    }
  }

  private promptText(arresting: boolean): string {
    if (arresting) return "Harbor Watch is cuffing you";
    if (this.occupied) return "E — Exit vehicle";
    if (this.nearby) {
      const tag = this.nearby.id === MISSION_VEHICLE_ID ? " (Night Circuit)" : "";
      return `E — Enter ${this.nearby.label()}${tag}`;
    }
    return "";
  }

  private tryInteract(): void {
    if (this.occupied) {
      const side = 2.1;
      const x = this.occupied.x + Math.cos(this.occupied.heading) * side;
      const z = this.occupied.z - Math.sin(this.occupied.heading) * side;
      this.occupied.occupied = false;
      if (this.occupied.id.startsWith("traffic-")) this.occupied.traffic = true;
      this.occupied = null;
      this.player.inVehicle = false;
      this.player.setPosition(x, z, this.follow.yaw);
      this.audio.blip(360, 0.07);
      return;
    }
    if (!this.nearby || this.nearby.kind === "watch") return;
    this.occupied = this.nearby;
    this.occupied.occupied = true;
    this.occupied.traffic = false;
    this.player.inVehicle = true;
    this.audio.blip(480, 0.08);
  }

  private findNearbyVehicle(): Vehicle | null {
    let best: Vehicle | null = null;
    let bestD = 4.3;
    for (const car of this.vehicles) {
      if (!car.group.visible || car.kind === "watch") continue;
      const d = Math.hypot(car.x - this.player.x, car.z - this.player.z);
      if (d < bestD) {
        best = car;
        bestD = d;
      }
    }
    return best;
  }

  private unstickFromCars(cars: Vehicle[]): void {
    for (const car of cars) {
      if (!car.group.visible) continue;
      const sep = separateCircles(this.player.x, this.player.z, this.player.radius, car.x, car.z, car.radius * 0.82);
      if (!sep) continue;
      this.player.x = sep.ax;
      this.player.z = sep.az;
      this.player.group.position.set(this.player.x, this.player.y, this.player.z);
    }
  }

  private requestLock(): void {
    this.canvas.focus();
    const lock = this.canvas.requestPointerLock?.();
    if (lock && typeof (lock as Promise<void>).catch === "function") {
      (lock as Promise<void>).catch(() => {
        /* fallback: hold right mouse */
      });
    }
  }

  private exitLock(): void {
    if (document.pointerLockElement) document.exitPointerLock();
  }

  private onCanvasClick = (): void => {
    this.audio.unlock();
    if (this.phase === "playing") this.requestLock();
  };

  private onPointerLock = (): void => {
    this.input.pointerLocked = document.pointerLockElement === this.canvas;
  };

  private onResize = (): void => {
    const w = window.innerWidth;
    const h = window.innerHeight;
    this.camera.aspect = w / Math.max(1, h);
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  };
}

function nearestRoad(value: number): number {
  const roads = [-80, -40, 0, 40, 80];
  return roads.reduce((best, road) => (Math.abs(road - value) < Math.abs(best - value) ? road : best));
}

function roadRoute(ax: number, az: number, bx: number, bz: number): { x: number; z: number }[] {
  const rx0 = nearestRoad(ax);
  const rz0 = nearestRoad(az);
  const rx1 = nearestRoad(bx);
  const rz1 = nearestRoad(bz);
  const raw = [
    { x: rx0, z: az },
    { x: rx0, z: rz0 },
    { x: rx1, z: rz0 },
    { x: rx1, z: rz1 },
    { x: bx, z: bz }
  ];
  const pts: { x: number; z: number }[] = [];
  for (const p of raw) {
    const prev = pts[pts.length - 1];
    if (!prev || Math.hypot(prev.x - p.x, prev.z - p.z) > 3) pts.push(p);
  }
  return pts;
}
