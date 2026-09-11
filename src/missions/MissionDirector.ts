import { MISSION_VEHICLE_ID, type LandmarkMap } from "../core/types";

export type MissionStage =
  | "go_market"
  | "take_vehicle"
  | "go_depot"
  | "lose_heat"
  | "go_safehouse"
  | "complete";

export interface MissionStatus {
  stage: MissionStage;
  objective: string;
  marker: { x: number; z: number } | null;
  raiseWanted?: number;
  reward?: number;
  justCompleted?: boolean;
}

export interface MissionInput {
  playerX: number;
  playerZ: number;
  inVehicle: boolean;
  vehicleId: string | null;
  wantedLevel: number;
}

const REACH = 18;

export class MissionDirector {
  stage: MissionStage = "go_market";
  private raisedOnRoute = false;
  private raisedAtDepot = false;
  readonly reward = 2500;

  reset(): void {
    this.stage = "go_market";
    this.raisedOnRoute = false;
    this.raisedAtDepot = false;
  }

  skipToRoam(): void {
    this.stage = "complete";
    this.raisedOnRoute = true;
    this.raisedAtDepot = true;
  }

  update(input: MissionInput, landmarks: LandmarkMap): MissionStatus {
    const status: MissionStatus = {
      stage: this.stage,
      objective: this.objectiveText(),
      marker: this.marker(landmarks)
    };

    if (this.stage === "go_market" && near(input, landmarks.market)) {
      this.stage = "take_vehicle";
    } else if (
      this.stage === "take_vehicle" &&
      input.inVehicle &&
      input.vehicleId === MISSION_VEHICLE_ID
    ) {
      this.stage = "go_depot";
    } else if (this.stage === "go_depot") {
      if (!this.raisedOnRoute && input.vehicleId === MISSION_VEHICLE_ID && input.inVehicle) {
        const leftMarket = !near(input, landmarks.market, 22);
        if (leftMarket) {
          this.raisedOnRoute = true;
          status.raiseWanted = 2;
        }
      }
      if (near(input, landmarks.depot)) {
        this.stage = "lose_heat";
        if (!this.raisedAtDepot) {
          this.raisedAtDepot = true;
          status.raiseWanted = Math.max(status.raiseWanted ?? 0, 3);
        }
      }
    } else if (this.stage === "lose_heat" && input.wantedLevel <= 0) {
      this.stage = "go_safehouse";
    } else if (this.stage === "go_safehouse" && near(input, landmarks.safehouse)) {
      this.stage = "complete";
      status.justCompleted = true;
      status.reward = this.reward;
    }

    status.stage = this.stage;
    status.objective = this.objectiveText();
    status.marker = this.marker(landmarks);
    return status;
  }

  objectiveText(): string {
    switch (this.stage) {
      case "go_market":
        return "Reach Midnight Market";
      case "take_vehicle":
        return "Enter the marked Volt Runner";
      case "go_depot":
        return "Drive the Volt Runner to Cyan Rail Depot";
      case "lose_heat":
        return "Lose Harbor Watch — stay unseen until the heat drops";
      case "go_safehouse":
        return "Deliver to the Harbor Lights safehouse";
      default:
        return "Night Circuit complete — Harbor Grid is open";
    }
  }

  marker(landmarks: LandmarkMap): { x: number; z: number } | null {
    switch (this.stage) {
      case "go_market":
        return landmarks.market;
      case "take_vehicle":
        return landmarks.market;
      case "go_depot":
        return landmarks.depot;
      case "lose_heat":
        return null;
      case "go_safehouse":
        return landmarks.safehouse;
      default:
        return null;
    }
  }
}

function near(input: MissionInput, point: { x: number; z: number }, radius = REACH): boolean {
  return Math.hypot(input.playerX - point.x, input.playerZ - point.z) < radius;
}
