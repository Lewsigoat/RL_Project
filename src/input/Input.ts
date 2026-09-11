export class Input {
  readonly keys = new Set<string>();
  mouseDX = 0;
  mouseDY = 0;
  lookHeld = false;
  pointerLocked = false;
  fireHeld = false;
  private interactQueued = false;
  private fireQueued = false;
  private pauseQueued = false;

  attach(canvas: HTMLCanvasElement): void {
    window.addEventListener("keydown", this.onKeyDown);
    window.addEventListener("keyup", this.onKeyUp);
    window.addEventListener("blur", this.clear);
    canvas.addEventListener("mousedown", this.onMouseDown);
    window.addEventListener("mouseup", this.onMouseUp);
    window.addEventListener("mousemove", this.onMouseMove);
    document.addEventListener("pointerlockchange", this.onLock);
    canvas.addEventListener("contextmenu", (e) => e.preventDefault());
  }

  detach(): void {
    window.removeEventListener("keydown", this.onKeyDown);
    window.removeEventListener("keyup", this.onKeyUp);
    window.removeEventListener("blur", this.clear);
    window.removeEventListener("mouseup", this.onMouseUp);
    window.removeEventListener("mousemove", this.onMouseMove);
    document.removeEventListener("pointerlockchange", this.onLock);
  }

  consumeMouse(): { x: number; y: number } {
    const out = { x: this.mouseDX, y: this.mouseDY };
    this.mouseDX = 0;
    this.mouseDY = 0;
    return out;
  }

  consumeInteract(): boolean {
    const v = this.interactQueued;
    this.interactQueued = false;
    return v;
  }

  consumeFire(): boolean {
    const v = this.fireQueued;
    this.fireQueued = false;
    return v;
  }

  queueFire(): void {
    this.fireQueued = true;
  }

  consumePause(): boolean {
    const v = this.pauseQueued;
    this.pauseQueued = false;
    return v;
  }

  axis(): { x: number; y: number } {
    let x = 0;
    let y = 0;
    if (this.keys.has("KeyA") || this.keys.has("ArrowLeft")) x -= 1;
    if (this.keys.has("KeyD") || this.keys.has("ArrowRight")) x += 1;
    if (this.keys.has("KeyW") || this.keys.has("ArrowUp")) y += 1;
    if (this.keys.has("KeyS") || this.keys.has("ArrowDown")) y -= 1;
    const mag = Math.hypot(x, y);
    if (mag > 1) {
      x /= mag;
      y /= mag;
    }
    return { x, y };
  }

  lookKeys(): { x: number; y: number } {
    let x = 0;
    let y = 0;
    if (this.keys.has("KeyQ")) x -= 1;
    if (this.keys.has("KeyC")) x += 1;
    if (this.keys.has("KeyR")) y -= 1;
    if (this.keys.has("KeyF")) y += 1;
    return { x, y };
  }

  sprint(): boolean {
    return this.keys.has("ShiftLeft") || this.keys.has("ShiftRight");
  }

  jump(): boolean {
    return this.keys.has("Space");
  }

  private onKeyDown = (event: KeyboardEvent): void => {
    if (event.code === "Space") event.preventDefault();
    this.keys.add(event.code);
    if (event.code === "KeyE") this.interactQueued = true;
    if (event.code === "Escape") this.pauseQueued = true;
  };

  private onKeyUp = (event: KeyboardEvent): void => {
    this.keys.delete(event.code);
  };

  private onMouseDown = (event: MouseEvent): void => {
    if (event.button === 0) {
      this.fireHeld = true;
      this.fireQueued = true;
    }
    if (event.button === 2) this.lookHeld = true;
  };

  private onMouseUp = (event: MouseEvent): void => {
    if (event.button === 0) this.fireHeld = false;
    if (event.button === 2) this.lookHeld = false;
  };

  private onMouseMove = (event: MouseEvent): void => {
    if (this.pointerLocked || this.lookHeld) {
      this.mouseDX += event.movementX;
      this.mouseDY += event.movementY;
    }
  };

  private onLock = (): void => {
    this.pointerLocked = document.pointerLockElement !== null;
  };

  private clear = (): void => {
    this.keys.clear();
    this.fireHeld = false;
    this.lookHeld = false;
  };
}
