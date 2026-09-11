import type { FailReason, GamePhase } from "../core/types";

const ONBOARD = [
  {
    title: "How you move",
    body: "WASD walks the Harbor Grid. Shift sprints. Space jumps. Mouse looks. If look-lock is blocked, hold right mouse or use Q/C and R/F to look."
  },
  {
    title: "Cars of the Grid",
    body: "Press E near a vehicle to climb in. Drive with WASD, Space for the handbrake, E to bail. Speed shows on the radar stack."
  },
  {
    title: "Heat and Harbor Watch",
    body: "Left click fires a compact pulse. Crimes raise Watch Level from 0 to 5. Stay unseen and leave the last known street to drop heat."
  },
  {
    title: "Night Circuit",
    body: "Hit Midnight Market, take the Volt Runner, punch through Cyan Rail Depot while the Watch is on you, lose them, then dock at Harbor Lights."
  }
];

export class Screens {
  readonly title = document.querySelector("#title-screen") as HTMLElement;
  readonly onboard = document.querySelector("#onboarding") as HTMLElement;
  readonly pause = document.querySelector("#pause-screen") as HTMLElement;
  readonly fail = document.querySelector("#fail-screen") as HTMLElement;
  readonly complete = document.querySelector("#complete-screen") as HTMLElement;
  readonly continueBtn = document.querySelector("#btn-continue") as HTMLButtonElement;
  readonly onboardTitle = document.querySelector("#onboard-title") as HTMLElement;
  readonly onboardBody = document.querySelector("#onboard-body") as HTMLElement;
  readonly failTitle = document.querySelector("#fail-title") as HTMLElement;
  readonly failBody = document.querySelector("#fail-body") as HTMLElement;
  readonly completeBody = document.querySelector("#complete-body") as HTMLElement;
  readonly sens = document.querySelector("#sens-slider") as HTMLInputElement;
  readonly vol = document.querySelector("#vol-slider") as HTMLInputElement;
  step = 0;

  constructor(
    handlers: {
      onStart: () => void;
      onContinue: () => void;
      onOnboardNext: () => void;
      onResume: () => void;
      onRestart: () => void;
      onTitle: () => void;
      onRoam: () => void;
      onSens: (v: number) => void;
      onVol: (v: number) => void;
    }
  ) {
    document.querySelector("#btn-start")!.addEventListener("click", handlers.onStart);
    this.continueBtn.addEventListener("click", handlers.onContinue);
    document.querySelector("#btn-onboard-next")!.addEventListener("click", handlers.onOnboardNext);
    document.querySelector("#btn-resume")!.addEventListener("click", handlers.onResume);
    document.querySelector("#btn-restart")!.addEventListener("click", handlers.onRestart);
    document.querySelector("#btn-title")!.addEventListener("click", handlers.onTitle);
    document.querySelector("#btn-fail-restart")!.addEventListener("click", handlers.onRestart);
    document.querySelector("#btn-fail-title")!.addEventListener("click", handlers.onTitle);
    document.querySelector("#btn-roam")!.addEventListener("click", handlers.onRoam);
    document.querySelector("#btn-complete-restart")!.addEventListener("click", handlers.onRestart);
    document.querySelector("#btn-complete-title")!.addEventListener("click", handlers.onTitle);
    this.sens.addEventListener("input", () => handlers.onSens(Number(this.sens.value)));
    this.vol.addEventListener("input", () => handlers.onVol(Number(this.vol.value)));
  }

  showOnboard(): void {
    const card = ONBOARD[this.step]!;
    this.onboardTitle.textContent = card.title;
    this.onboardBody.textContent = card.body;
    const btn = document.querySelector("#btn-onboard-next") as HTMLButtonElement;
    btn.textContent = this.step >= ONBOARD.length - 1 ? "Hit the streets" : "Next";
  }

  nextOnboard(): boolean {
    if (this.step >= ONBOARD.length - 1) {
      this.step = 0;
      return true;
    }
    this.step += 1;
    this.showOnboard();
    return false;
  }

  setContinueEnabled(on: boolean): void {
    this.continueBtn.style.display = on ? "" : "none";
  }

  setSliders(sens: number, vol: number): void {
    this.sens.value = String(sens);
    this.vol.value = String(vol);
  }

  setFail(reason: FailReason): void {
    if (reason === "arrested") {
      this.failTitle.textContent = "Cuffed";
      this.failBody.textContent = "Harbor Watch closed the distance and ended the Circuit.";
    } else {
      this.failTitle.textContent = "Downed";
      this.failBody.textContent = "Your vitals hit empty on the Grid. The drop is cold.";
    }
  }

  setComplete(money: number): void {
    this.completeBody.textContent = `The Watch lost the trail. Harbor Lights wired NC$ ${money} into your jacket.`;
  }

  apply(phase: GamePhase): void {
    this.title.classList.toggle("hidden", phase !== "title");
    this.onboard.classList.toggle("hidden", phase !== "onboarding");
    this.pause.classList.toggle("hidden", phase !== "paused");
    this.fail.classList.toggle("hidden", phase !== "failed");
    this.complete.classList.toggle("hidden", phase !== "complete");
  }
}
