import { describe, expect, it } from "vitest";
import { MISSION_VEHICLE_ID, type LandmarkMap } from "../core/types";
import { MissionDirector } from "./MissionDirector";

const landmarks: LandmarkMap = {
  market: { x: 0, z: 0 },
  depot: { x: 40, z: 0 },
  safehouse: { x: 80, z: 0 },
  plaza: { x: 0, z: 20 },
  canal: { x: -40, z: 0 }
};

describe("Night Circuit mission", () => {
  it("walks through every required stage", () => {
    const mission = new MissionDirector();
    expect(mission.update({ playerX: 100, playerZ: 100, inVehicle: false, vehicleId: null, wantedLevel: 0 }, landmarks).stage).toBe(
      "go_market"
    );

    expect(mission.update({ playerX: 0, playerZ: 0, inVehicle: false, vehicleId: null, wantedLevel: 0 }, landmarks).stage).toBe(
      "take_vehicle"
    );

    const boarded = mission.update(
      { playerX: 0, playerZ: 0, inVehicle: true, vehicleId: MISSION_VEHICLE_ID, wantedLevel: 0 },
      landmarks
    );
    expect(boarded.stage).toBe("go_depot");

    const leaving = mission.update(
      { playerX: 24, playerZ: 0, inVehicle: true, vehicleId: MISSION_VEHICLE_ID, wantedLevel: 0 },
      landmarks
    );
    expect(leaving.raiseWanted).toBe(2);

    const depot = mission.update(
      { playerX: 40, playerZ: 0, inVehicle: true, vehicleId: MISSION_VEHICLE_ID, wantedLevel: 2 },
      landmarks
    );
    expect(depot.stage).toBe("lose_heat");
    expect(depot.raiseWanted).toBe(3);

    expect(
      mission.update({ playerX: 40, playerZ: 0, inVehicle: true, vehicleId: MISSION_VEHICLE_ID, wantedLevel: 0 }, landmarks).stage
    ).toBe("go_safehouse");

    const done = mission.update({ playerX: 80, playerZ: 0, inVehicle: false, vehicleId: null, wantedLevel: 0 }, landmarks);
    expect(done.stage).toBe("complete");
    expect(done.justCompleted).toBe(true);
    expect(done.reward).toBe(2500);
  });
});
