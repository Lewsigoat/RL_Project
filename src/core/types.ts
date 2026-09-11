export type GamePhase = "title" | "onboarding" | "playing" | "paused" | "failed" | "complete";

export type FailReason = "arrested" | "downed";

export interface AABB {
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
  minY: number;
  maxY: number;
}

export interface SaveData {
  version: 1;
  money: number;
  missionCompleted: boolean;
  mouseSensitivity: number;
  volume: number;
  bestWanted: number;
}

export const SAVE_KEY = "neon-county-save-v1";

export const CITY_HALF = 100;
export const ROAD_COORDS = [-80, -40, 0, 40, 80] as const;
export const ROAD_WIDTH = 11;
export const LANE_OFFSET = 2.7;
export const SIDEWALK = 2.35;

export const PLAYER_WALK = 5.3;
export const PLAYER_SPRINT = 8.9;
export const PLAYER_RADIUS = 0.42;

export const MISSION_VEHICLE_ID = "volt-runner";

export interface LandmarkMap {
  market: { x: number; z: number };
  depot: { x: number; z: number };
  safehouse: { x: number; z: number };
  plaza: { x: number; z: number };
  canal: { x: number; z: number };
}

export function defaultSave(): SaveData {
  return {
    version: 1,
    money: 180,
    missionCompleted: false,
    mouseSensitivity: 1,
    volume: 0.55,
    bestWanted: 0
  };
}
