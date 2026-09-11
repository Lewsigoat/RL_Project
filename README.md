# Neon County

Original browser 3D open-world crime-action vertical slice set in **Harbor Grid**, a compact night district in Neon County. The drop is **Night Circuit**: reach Midnight Market, take the Volt Runner, hit Cyan Rail Depot under Harbor Watch heat, lose the pursuit, and dock at the Harbor Lights safehouse.

The project is self-contained. Geometry, signs, audio, and UI are procedural or written in-repo. Nothing here copies Rockstar names, maps, characters, UI, vehicles, or music.

## Setup

Requires Node.js 20+.

```bash
npm install
```

## Run

```bash
npm run dev
```

Open the printed local URL (default `http://localhost:5173`). Click the streets to look around.

## Build / checks

```bash
npm test
npm run typecheck
npm run lint
npm run build
npm run preview
```

`lint` is the TypeScript compiler in no-emit mode. `preview` serves the production bundle on port 4173.

## Controls

| Input | Action |
| --- | --- |
| `W A S D` / arrows | Walk or drive |
| `Shift` | Sprint |
| `Space` | Jump on foot / handbrake while driving |
| `E` | Enter, exit, interact |
| Mouse | Orbit camera and aim |
| Left click | Fire |
| `Esc` | Pause / help |
| Right mouse | Look when pointer lock is blocked |
| `Q` / `C` | Look left / right without pointer lock |
| `R` / `F` | Look up / down without pointer lock |

## Architecture

| Area | Path |
| --- | --- |
| Boot + loop | `src/main.ts`, `src/core/Game.ts` |
| City + collision | `src/world/City.ts`, `src/world/CollisionWorld.ts` |
| Player / camera | `src/player/Player.ts`, `src/camera/GameCamera.ts` |
| Vehicles / traffic | `src/vehicles/Vehicle.ts` |
| Pedestrians / Watch | `src/npcs/Pedestrian.ts`, `src/npcs/PoliceDirector.ts` |
| Heat | `src/wanted/WantedSystem.ts` |
| Combat | `src/combat/CombatSystem.ts` |
| Night Circuit | `src/missions/MissionDirector.ts` |
| HUD / radar / menus | `src/ui/` |
| Day-night + audio + save | `src/time/DayNight.ts`, `src/audio/AudioEngine.ts`, `src/persist/SaveStore.ts` |

Progress (credits, completed Circuit, look/volume) writes to `localStorage` key `neon-county-save-v1`.

## Known limitations

- Arcade collision, not a full physics engine. Vehicles slide along buildings.
- Harbor Watch uses a capped pool (4 on foot, 3 interceptors).
- Gunplay is a short-range pulse with no gore.
- Traffic follows fixed district loops and brakes for blockers instead of full pathfinding.
- Synth audio is generated in the browser; there is no streamed music bed.

## Legacy files

`archive/legacy-rl/` holds the previous pygame Q-learning racer that used to be the repository root. It is not part of Neon County.
