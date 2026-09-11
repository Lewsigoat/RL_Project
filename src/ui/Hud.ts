export class Hud {
  private readonly health = document.querySelector("#health-fill") as HTMLElement;
  private readonly pips = document.querySelector("#wanted-pips") as HTMLElement;
  private readonly money = document.querySelector("#money-readout") as HTMLElement;
  private readonly objective = document.querySelector("#objective") as HTMLElement;
  private readonly prompt = document.querySelector("#prompt") as HTMLElement;
  private readonly speed = document.querySelector("#speed-readout") as HTMLElement;
  private readonly clock = document.querySelector("#clock-readout") as HTMLElement;
  private readonly lookHint = document.querySelector("#look-hint") as HTMLElement;
  private readonly hud = document.querySelector("#hud") as HTMLElement;
  private readonly flash = document.querySelector("#damage-flash") as HTMLElement;
  private flashUntil = 0;

  constructor() {
    this.pips.innerHTML = Array.from({ length: 5 }, () => "<span></span>").join("");
  }

  setVisible(on: boolean): void {
    this.hud.classList.toggle("hidden", !on);
  }

  pulseDamage(now: number): void {
    this.flashUntil = now + 0.18;
    this.flash.classList.add("show");
  }

  update(opts: {
    now: number;
    health: number;
    wanted: number;
    money: number;
    objective: string;
    prompt: string;
    driving: boolean;
    kmh: number;
    clock: string;
    showLookHint: boolean;
  }): void {
    this.health.style.transform = `scaleX(${Math.max(0, opts.health / 100)})`;
    [...this.pips.children].forEach((el, i) => {
      el.classList.toggle("on", i < opts.wanted);
    });
    this.money.textContent = `NC$ ${Math.floor(opts.money)}`;
    this.objective.textContent = opts.objective;
    this.prompt.textContent = opts.prompt;
    this.speed.classList.toggle("hidden", !opts.driving);
    this.speed.innerHTML = `${Math.round(opts.kmh)} <small>km/h</small>`;
    this.clock.textContent = opts.clock;
    this.lookHint.classList.toggle("hidden", !opts.showLookHint);
    if (opts.now > this.flashUntil) this.flash.classList.remove("show");
  }
}
