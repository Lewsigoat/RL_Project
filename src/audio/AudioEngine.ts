export class AudioEngine {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private engine: OscillatorNode | null = null;
  private engineGain: GainNode | null = null;
  private pad: OscillatorNode | null = null;
  private siren: OscillatorNode | null = null;
  private sirenGain: GainNode | null = null;
  private sirenTimer = 0;
  private sirenHigh = true;
  volume = 0.55;
  muted = false;

  unlock(): void {
    if (this.ctx) return;
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    this.ctx = new Ctx();
    this.master = this.ctx.createGain();
    this.master.gain.value = this.volume;
    this.master.connect(this.ctx.destination);

    this.engine = this.ctx.createOscillator();
    this.engine.type = "sawtooth";
    this.engine.frequency.value = 48;
    this.engineGain = this.ctx.createGain();
    this.engineGain.gain.value = 0;
    const filter = this.ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = 420;
    this.engine.connect(filter);
    filter.connect(this.engineGain);
    this.engineGain.connect(this.master);
    this.engine.start();

    this.pad = this.ctx.createOscillator();
    this.pad.type = "sine";
    this.pad.frequency.value = 92;
    const padGain = this.ctx.createGain();
    padGain.gain.value = 0.03;
    this.pad.connect(padGain);
    padGain.connect(this.master);
    this.pad.start();

    this.siren = this.ctx.createOscillator();
    this.siren.type = "triangle";
    this.siren.frequency.value = 620;
    this.sirenGain = this.ctx.createGain();
    this.sirenGain.gain.value = 0;
    this.siren.connect(this.sirenGain);
    this.sirenGain.connect(this.master);
    this.siren.start();
  }

  setVolume(value: number): void {
    this.volume = value;
    if (this.master) this.master.gain.value = this.muted ? 0 : value;
  }

  blip(freq = 520, dur = 0.08): void {
    this.tone(freq, dur, 0.08, "square");
  }

  sting(): void {
    this.tone(180, 0.18, 0.12, "sawtooth");
    this.tone(320, 0.22, 0.08, "square");
  }

  success(): void {
    this.tone(440, 0.12, 0.09, "triangle");
    this.tone(554, 0.14, 0.08, "triangle");
    this.tone(659, 0.2, 0.1, "triangle");
  }

  gunshot(): void {
    if (!this.ctx || !this.master) return;
    const dur = 0.12;
    const buffer = this.ctx.createBuffer(1, this.ctx.sampleRate * dur, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i += 1) {
      data[i] = (Math.random() * 2 - 1) * (1 - i / data.length);
    }
    const src = this.ctx.createBufferSource();
    src.buffer = buffer;
    const filter = this.ctx.createBiquadFilter();
    filter.type = "bandpass";
    filter.frequency.value = 1400;
    const gain = this.ctx.createGain();
    gain.gain.value = 0.28;
    src.connect(filter);
    filter.connect(gain);
    gain.connect(this.master);
    src.start();
  }

  update(dt: number, driving: boolean, speed: number, wanted: number): void {
    if (!this.ctx || !this.engine || !this.engineGain || !this.siren || !this.sirenGain) return;
    if (this.ctx.state === "suspended") void this.ctx.resume();
    const target = driving ? 0.045 + Math.min(0.08, speed * 0.002) : 0;
    this.engineGain.gain.value += (target - this.engineGain.gain.value) * Math.min(1, dt * 8);
    this.engine.frequency.value = 42 + speed * 4.2;
    const sirenOn = wanted >= 2;
    this.sirenGain.gain.value += ((sirenOn ? 0.035 : 0) - this.sirenGain.gain.value) * Math.min(1, dt * 6);
    this.sirenTimer += dt;
    if (this.sirenTimer > 0.36) {
      this.sirenTimer = 0;
      this.sirenHigh = !this.sirenHigh;
      this.siren.frequency.value = this.sirenHigh ? 740 : 510;
    }
  }

  private tone(freq: number, dur: number, gain: number, type: OscillatorType): void {
    if (!this.ctx || !this.master) return;
    const osc = this.ctx.createOscillator();
    const g = this.ctx.createGain();
    osc.type = type;
    osc.frequency.value = freq;
    g.gain.value = gain;
    g.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + dur);
    osc.connect(g);
    g.connect(this.master);
    osc.start();
    osc.stop(this.ctx.currentTime + dur);
  }
}
