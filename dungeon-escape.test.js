/*
 * Headless verification suite for dungeon-escape.html.
 *
 * Drives the real game in a headless Chromium through the window.DungeonEscape
 * test API: it owns the clock (pauseLoop + fixed-step step()), presses keys the
 * way a player would, and asserts on the resulting simulation state. Nothing is
 * mocked - every check runs against the shipped file.
 *
 * Optional tooling; not required to play the game. To run it:
 *     npm install playwright        # or have it available on NODE_PATH
 *     node dungeon-escape.test.js [path/to/dungeon-escape.html]
 *
 * Exits non-zero if any check fails.
 */
const { chromium } = require('playwright');
const path = require('path');

const FILE = 'file://' + path.resolve(process.argv[2] || '/home/user/RL_Project/dungeon-escape.html');

let pass = 0, fail = 0;
const failures = [];
function check(name, ok, detail) {
  if (ok) { pass++; console.log('  \x1b[32mPASS\x1b[0m ' + name); }
  else { fail++; failures.push(name + (detail ? ' :: ' + detail : '')); console.log('  \x1b[31mFAIL\x1b[0m ' + name + (detail ? '  -> ' + detail : '')); }
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1200, height: 900 } });

  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console.error: ' + m.text()); });

  await page.goto(FILE);
  await page.waitForFunction(() => !!window.DungeonEscape, null, { timeout: 10000 });
  // let a few frames run so rAF / render path is exercised
  await page.waitForTimeout(600);

  console.log('\n== 0. Boot ==');
  check('no page/console errors on boot', errors.length === 0, errors.join(' | '));
  check('test API present', await page.evaluate(() => typeof window.DungeonEscape.step === 'function'));
  check('render loop ran', await page.evaluate(() => window.DungeonEscape.isRunning()));

  // Take ownership of the clock for everything below.
  await page.evaluate(() => window.DungeonEscape.pauseLoop());

  /* ------------------------------------------------------------------ */
  console.log('\n== 1. Derived jump physics ==');
  const phys = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    return {
      rise: D.maxJumpRisePx(),
      riseTiles: D.maxJumpRisePx() / C.TILE,
      g3: D.maxGapTiles(3), g2: D.maxGapTiles(2), g1: D.maxGapTiles(1),
      g0: D.maxGapTiles(0), gm2: D.maxGapTiles(-2), gm4: D.maxGapTiles(-4),
      g4: D.maxGapTiles(4)
    };
  });
  check('max jump rise clears 3 tiles', phys.riseTiles > 3.1 && phys.riseTiles < 5,
        'rise=' + phys.rise.toFixed(1) + 'px (' + phys.riseTiles.toFixed(2) + ' tiles)');
  check('gap budget shrinks as the climb gets taller',
        phys.g3 <= phys.g2 && phys.g2 <= phys.g0 && phys.g0 <= phys.gm4,
        JSON.stringify(phys));
  check('a 4-tile climb is rejected as unreachable', phys.g4 < 1, 'g4=' + phys.g4);
  check('all generator-usable gaps are >= 1 tile', phys.g3 >= 1 && phys.g0 >= 1, JSON.stringify(phys));

  /* ------------------------------------------------------------------ */
  console.log('\n== 2. Level generation (200 seeds) ==');
  const gen = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    let bad = [], nulls = 0, minSegs = 1e9, maxSegs = 0, riseMax = -99, gapMax = 0;
    for (let s = 1; s <= 200; s++) {
      const L = D.generateLevel(s);
      if (!L) { nulls++; continue; }
      const err = D.validateLevel(L);
      if (err) { bad.push(s + ':' + err); continue; }
      minSegs = Math.min(minSegs, L.segs.length);
      maxSegs = Math.max(maxSegs, L.segs.length);
      for (let i = 0; i < L.segs.length - 1; i++) {
        riseMax = Math.max(riseMax, L.segs[i].top - L.segs[i + 1].top);
        gapMax = Math.max(gapMax, L.segs[i + 1].x - (L.segs[i].x + L.segs[i].len));
      }
    }
    return { bad, nulls, minSegs, maxSegs, riseMax, gapMax, W: C.MAP_W, H: C.MAP_H };
  });
  check('map is at least 50x20 tiles', gen.W >= 50 && gen.H >= 20, gen.W + 'x' + gen.H);
  check('no generated level fails validation', gen.bad.length === 0, gen.bad.slice(0, 5).join(', '));
  check('generator rejects less than 8% of seeds', gen.nulls < 16, 'nulls=' + gen.nulls + '/200');
  check('levels always have many ledges', gen.minSegs >= 9, 'min=' + gen.minSegs + ' max=' + gen.maxSegs);
  check('no climb exceeds 3 tiles', gen.riseMax <= 3, 'riseMax=' + gen.riseMax);

  const counts = await page.evaluate(() => {
    const D = window.DungeonEscape;
    let ok = true, detail = '';
    for (let s = 1; s <= 50; s++) {
      D.loadLevel(s);
      const L = D.level;
      if (L.coins.length !== 3 || L.enemies.length !== 2 || !L.door) {
        ok = false; detail = 'seed ' + s + ' coins=' + L.coins.length + ' enemies=' + L.enemies.length;
        break;
      }
      const kinds = L.enemies.map(e => e.kind).sort().join(',');
      if (kinds !== 'crawler,wisp') { ok = false; detail = 'seed ' + s + ' kinds=' + kinds; break; }
    }
    return { ok, detail };
  });
  check('every level has exactly 3 coins, 2 moving enemies, 1 door', counts.ok, counts.detail);

  const determinism = await page.evaluate(() => {
    const D = window.DungeonEscape;
    const a = D.generateLevel(4242), b = D.generateLevel(4242);
    if (!a || !b) return 'null level';
    if (a.grid.length !== b.grid.length) return 'len';
    for (let i = 0; i < a.grid.length; i++) if (a.grid[i] !== b.grid[i]) return 'grid@' + i;
    if (JSON.stringify(a.coins) !== JSON.stringify(b.coins)) return 'coins';
    return null;
  });
  check('same seed regenerates an identical dungeon', determinism === null, determinism);

  /* ------------------------------------------------------------------ */
  console.log('\n== 3. Collision: no clipping through solids ==');

  // Brute force: many random input sequences across several seeds; the player's
  // AABB must never overlap a solid tile at the end of any physics tick.
  const fuzz = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    function overlapsSolid() {
      const p = D.player;
      const x0 = Math.floor(p.x / C.TILE), x1 = Math.floor((p.x + p.w - 0.001) / C.TILE);
      const y0 = Math.floor(p.y / C.TILE), y1 = Math.floor((p.y + p.h - 0.001) / C.TILE);
      for (let cy = y0; cy <= y1; cy++)
        for (let cx = x0; cx <= x1; cx++)
          if (D.isSolid(D.tileAt(cx, cy))) return { cx, cy, px: p.x, py: p.y };
      return null;
    }
    let rngState = 12345;
    const rnd = () => (rngState = (rngState * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
    let violations = [], ticks = 0;
    for (let seed = 1; seed <= 8; seed++) {
      D.loadLevel(seed);
      D.start();
      D.clearKeys();
      for (let t = 0; t < 5000; t++) {
        if (t % 7 === 0) {
          D.setKey('left', rnd() < 0.35);
          D.setKey('right', rnd() < 0.45);
          D.setKey('down', rnd() < 0.15);
        }
        if (t % 5 === 0) D.setKey('jump', rnd() < 0.55);
        D.step(C.FIXED_DT);
        ticks++;
        const v = overlapsSolid();
        if (v) { violations.push('seed' + seed + ' t' + t + ' ' + JSON.stringify(v)); break; }
        // keep the run alive so it keeps exploring
        if (D.game.state !== 'playing') { D.game.lives = 3; D.game.state = 'playing'; }
      }
    }
    return { violations, ticks };
  });
  check('player never ends a tick inside a solid tile (40k random-input ticks)',
        fuzz.violations.length === 0, fuzz.violations.slice(0, 3).join(' | ') + ' ticks=' + fuzz.ticks);

  // Targeted corner test: drive hard into the seam where a ledge meets a drop,
  // from every approach direction. This is where naive single-pass AABB
  // resolution squeezes the player through.
  const corner = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    const violations = [];
    function firstOverlap() {
      const p = D.player;
      const x0 = Math.floor(p.x / C.TILE), x1 = Math.floor((p.x + p.w - 0.001) / C.TILE);
      const y0 = Math.floor(p.y / C.TILE), y1 = Math.floor((p.y + p.h - 0.001) / C.TILE);
      for (let cy = y0; cy <= y1; cy++)
        for (let cx = x0; cx <= x1; cx++)
          if (D.isSolid(D.tileAt(cx, cy))) return { cx, cy, x: +p.x.toFixed(2), y: +p.y.toFixed(2) };
      return null;
    }
    for (let seed = 3; seed <= 10; seed++) {
      D.loadLevel(seed); D.restart();
      const L = D.level;
      for (let i = 0; i < L.segs.length - 1; i++) {
        const a = L.segs[i];
        const edge = a.x + a.len;                     // column just past the ledge
        // Four approaches at the ledge/drop seam, including landing straight
        // onto the corner from above while moving sideways.
        const b = L.segs[i + 1];
        const high = Math.min(a.top, b.top);          // the higher of the two ledges
        const air = (high - 5) * C.TILE;              // clear of both surfaces
        const approaches = [
          { x: (edge - 2) * C.TILE,   y: a.top * C.TILE - C.PLAYER_H, keys: ['right'], vy: 0 },
          { x: (edge - 0.4) * C.TILE, y: air, keys: ['right'], vy: 900 },
          { x: (edge - 0.4) * C.TILE, y: air, keys: ['left'],  vy: 900 },
          { x: (b.x + 0.4) * C.TILE,  y: air, keys: ['left'],  vy: 900 },
          { x: (b.x + 0.4) * C.TILE,  y: air, keys: ['right'], vy: 900 }
        ];
        for (const ap of approaches) {
          D.clearKeys();
          D.teleport(ap.x, ap.y);
          D.player.vy = ap.vy;
          D.player.invuln = 1e9;                      // geometry test, not combat
          ap.keys.forEach(k => D.setKey(k, true));
          if (firstOverlap()) continue;   // invalid start position, not a game failure
          for (let t = 0; t < 200; t++) {
            D.player.invuln = 1e9;
            D.step(C.FIXED_DT);
            const v = firstOverlap();
            if (v) { violations.push('seed' + seed + ' seg' + i + ' ' + ap.keys[0] + ' t' + t + ' ' + JSON.stringify(v)); break; }
          }
          if (violations.length > 3) break;
        }
        if (violations.length > 3) break;
      }
      if (violations.length > 3) break;
    }
    D.clearKeys();
    return violations;
  });
  check('driving into ledge corners from every direction never embeds the player',
        corner.length === 0, corner.slice(0, 2).join(' | '));

  // Tunnelling: slam the player downward at far beyond terminal velocity.
  const tunnel = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    D.loadLevel(11); D.start();
    const seg = D.level.segs[2];
    let escaped = 0;
    for (let trial = 0; trial < 40; trial++) {
      D.teleport((seg.x + 2) * C.TILE, (seg.top - 6) * C.TILE);
      D.player.vy = 6000 + trial * 400;   // way past MAX_FALL, before capping
      D.player.vx = (trial % 2 ? 1 : -1) * 2500;
      for (let t = 0; t < 40; t++) D.step(C.FIXED_DT);
      // Must have come to rest on the ledge, not fallen through the world.
      if (D.player.y > (seg.top + 2) * C.TILE) escaped++;
    }
    return escaped;
  });
  check('extreme velocities cannot tunnel through a floor', tunnel === 0, 'escaped=' + tunnel);

  /* ------------------------------------------------------------------ */
  console.log('\n== 4. Movement feel: coyote time, buffering, variable jump ==');

  const coyote = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    // Walk off a ledge, wait `delay` seconds, then press jump.
    function trial(delay) {
      D.loadLevel(21); D.restart(); D.clearKeys();
      const L = D.level;
      let seg = null;
      for (let i = 0; i < L.segs.length - 1; i++) {
        if (L.segs[i + 1].x - (L.segs[i].x + L.segs[i].len) >= 2) { seg = L.segs[i]; break; }
      }
      if (!seg) return null;
      D.teleport((seg.x + seg.len - 3) * C.TILE, seg.top * C.TILE - C.PLAYER_H);
      D.player.invuln = 1e9;
      D.setKey('right', true);
      // run until airborne (walked off the edge)
      let guard = 0;
      while (D.player.grounded === false && guard++ < 200) D.step(C.FIXED_DT);   // settle onto ground
      guard = 0;
      while (D.player.grounded === true && guard++ < 400) D.step(C.FIXED_DT);    // run off the edge
      if (D.player.grounded) return null;
      // wait `delay`
      const n = Math.round(delay / C.FIXED_DT);
      for (let i = 0; i < n; i++) D.step(C.FIXED_DT);
      const vyBefore = D.player.vy;
      D.setKey('jump', true);
      D.step(C.FIXED_DT);
      const vyAfter = D.player.vy;
      D.setKey('jump', false);
      D.clearKeys();
      return { vyBefore, vyAfter, jumped: vyAfter < -C.JUMP_VEL * 0.7 };
    }
    return { early: trial(0.05), late: trial(0.30), COYOTE: C.COYOTE_TIME };
  });
  check('coyote time: jump works shortly after leaving a ledge',
        !!(coyote.early && coyote.early.jumped), JSON.stringify(coyote.early));
  check('coyote time expires (no free mid-air jump later)',
        !!(coyote.late && !coyote.late.jumped), JSON.stringify(coyote.late));

  const noDouble = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    D.loadLevel(21); D.restart(); D.clearKeys();
    const seg = D.level.segs[1];
    D.teleport((seg.x + 2) * C.TILE, seg.top * C.TILE - C.PLAYER_H);
    D.player.invuln = 1e9;
    for (let i = 0; i < 40; i++) D.step(C.FIXED_DT);   // land
    D.setKey('jump', true); D.step(C.FIXED_DT);
    const v1 = D.player.vy;
    for (let i = 0; i < 20; i++) D.step(C.FIXED_DT);
    D.setKey('jump', false); D.step(C.FIXED_DT);
    D.setKey('jump', true);                            // second press mid-air
    const before = D.player.vy;
    D.step(C.FIXED_DT);
    const after = D.player.vy;
    D.clearKeys();
    return { v1, before, after, doubled: after < before - 50 };
  });
  check('no double jump: a second mid-air press does nothing',
        noDouble.doubled === false, JSON.stringify(noDouble));

  const buffer = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    const seg0 = () => D.level.segs[1];
    function setup() {
      D.loadLevel(21); D.restart(); D.clearKeys();
      const seg = seg0();
      D.teleport((seg.x + 2) * C.TILE, (seg.top - 5) * C.TILE);
      D.player.vy = 0;
      D.player.invuln = 1e9;          // isolate the buffer logic from enemies/spikes
    }
    // Dry run: how many ticks does the fall take? No geometry assumptions.
    setup();
    let landTick = 0;
    while (landTick++ < 600 && !D.player.grounded) { D.player.invuln = 1e9; D.step(C.FIXED_DT); }

    // Real run: press jump `lead` ticks before touchdown and hold it, exactly as
    // a player would. A press inside the buffer window must fire on landing.
    function trial(leadTicks) {
      setup();
      const pressAt = Math.max(0, landTick - leadTicks);
      let airborneAgain = false, peakVy = 0;
      for (let t = 0; t < landTick + 30; t++) {
        if (t === pressAt) D.setKey('jump', true);
        D.player.invuln = 1e9;
        D.step(C.FIXED_DT);
        if (t > landTick - 2) {
          peakVy = Math.min(peakVy, D.player.vy);
          if (D.player.vy < -100 && !D.player.grounded) airborneAgain = true;
        }
      }
      D.clearKeys();
      return { jumped: airborneAgain, peakVy: +peakVy.toFixed(1) };
    }
    const within = trial(7);    // ~0.058s before landing (inside the 0.12s buffer)
    const beyond = trial(90);   // 0.75s before landing (well outside it)
    return { landTick, within, beyond, BUFFER: C.JUMP_BUFFER };
  });
  check('jump buffering: a press just before landing fires on touchdown',
        buffer.within.jumped === true, JSON.stringify(buffer));
  check('jump buffer expires (a very early press is forgotten)',
        buffer.beyond.jumped === false, JSON.stringify(buffer));

  const variable = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    function apex(holdSeconds) {
      D.loadLevel(21); D.restart(); D.clearKeys();
      const seg = D.level.segs[1];
      D.teleport((seg.x + 2) * C.TILE, seg.top * C.TILE - C.PLAYER_H);
    D.player.invuln = 1e9;
      for (let i = 0; i < 40; i++) D.step(C.FIXED_DT);
      const y0 = D.player.y;
      D.setKey('jump', true);
      const holdTicks = Math.round(holdSeconds / C.FIXED_DT);
      let best = y0;
      for (let i = 0; i < 400; i++) {
        if (i === holdTicks) D.setKey('jump', false);
        D.step(C.FIXED_DT);
        best = Math.min(best, D.player.y);
        if (i > holdTicks && D.player.grounded) break;
      }
      D.clearKeys();
      return y0 - best;   // pixels risen
    }
    return { tap: apex(0.02), medium: apex(0.12), hold: apex(1.0) };
  });
  check('variable jump: tapping produces a real but short hop',
        variable.tap > 20 && variable.tap < variable.hold * 0.75, JSON.stringify(variable));
  check('variable jump: height scales with hold duration',
        variable.tap < variable.medium && variable.medium < variable.hold, JSON.stringify(variable));
  check('full jump clears 3 tiles', variable.hold >= 96, 'hold=' + variable.hold.toFixed(1));

  /* ------------------------------------------------------------------ */
  console.log('\n== 5. Level is actually traversable (simulated play) ==');

  const traverse = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    // For every ledge-to-ledge transition in several dungeons, actually run the
    // player at it and confirm they land on the next ledge.
    const report = [];
    for (let seed = 1; seed <= 12; seed++) {
      D.loadLevel(seed); D.start();
      const L = D.level;
      for (let i = 0; i < L.segs.length - 1; i++) {
        const A = L.segs[i], B = L.segs[i + 1];
        const edge = (A.x + A.len) * C.TILE;
        const runFrom = Math.max((A.x + 0.2) * C.TILE, edge - 6 * C.TILE);
        D.clearKeys();
        D.teleport(runFrom, A.top * C.TILE - C.PLAYER_H);
        // Pure geometry/physics probe: enemies and spikes would otherwise
        // teleport the player back mid-run and corrupt the result.
        D.game.lives = 3; D.game.state = 'playing';
        D.player.invuln = 1e9;
        // settle onto the ledge
        for (let t = 0; t < 60; t++) D.step(C.FIXED_DT);
        D.setKey('right', true);
        let jumped = false, landed = false, ticks = 0, airborne = false;
        while (ticks++ < 700) {
          const p = D.player;
          p.invuln = 1e9;
          if (!jumped && p.x + p.w >= edge - 2) { D.setKey('jump', true); jumped = true; }
          D.step(C.FIXED_DT);
          if (jumped && !p.grounded) airborne = true;
          if (jumped && airborne && p.grounded) { landed = true; break; }
          if (p.y > C.MAP_H * C.TILE) break;
        }
        D.setKey('jump', false); D.setKey('right', false);
        const p = D.player;
        // Success = came to rest horizontally over ledge B, standing on B's
        // floor or on a plank hovering above it (both are recoverable footing).
        const feetRow = (p.y + p.h) / C.TILE;
        const onB = landed &&
                    p.x + p.w > B.x * C.TILE &&
                    p.x < (B.x + B.len) * C.TILE &&
                    feetRow <= B.top + 0.05 && feetRow >= B.top - 4;
        if (!onB) {
          report.push('seed' + seed + ' seg' + i + ' rise=' + (A.top - B.top) +
                      ' gap=' + (B.x - (A.x + A.len)) + ' landed=' + landed +
                      ' x=' + p.x.toFixed(0) + ' expectedX[' + (B.x * C.TILE) + ',' +
                      ((B.x + B.len) * C.TILE) + '] feetRow=' + feetRow.toFixed(2) +
                      ' Btop=' + B.top);
        }
      }
    }
    D.clearKeys();
    return report;
  });
  check('every jump in 12 dungeons is clearable by the real physics',
        traverse.length === 0, traverse.slice(0, 4).join(' | '));

  /* ------------------------------------------------------------------ */
  console.log('\n== 6. Coins, enemies, spikes, door, lives ==');

  const coinTest = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    D.loadLevel(33); D.restart();
    const before = { score: D.game.score, coins: D.game.coins };
    for (const c of D.level.coins) {
      D.teleport(c.x - C.PLAYER_W / 2, c.y - C.PLAYER_H / 2);
      D.step(C.FIXED_DT);
    }
    return { before, score: D.game.score, coins: D.game.coins, taken: D.level.coins.filter(c => c.taken).length };
  });
  check('all 3 coins collect and add score', coinTest.coins === 3 && coinTest.taken === 3 &&
        coinTest.score === coinTest.before.score + 300, JSON.stringify(coinTest));

  const doorLocked = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    D.loadLevel(33); D.restart();
    const d = D.level.door;
    D.teleport(d.x + 8, d.y + d.h - C.PLAYER_H);
    for (let i = 0; i < 30; i++) D.step(C.FIXED_DT);
    return { state: D.game.state, coins: D.game.coins, toast: D.game.toast && D.game.toast.text };
  });
  check('door stays locked until all coins are found', doorLocked.state === 'playing',
        JSON.stringify(doorLocked));
  check('locked door explains itself to the player', /Locked/.test(doorLocked.toast || ''),
        JSON.stringify(doorLocked.toast));

  const winTest = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    D.loadLevel(33); D.restart();
    for (const c of D.level.coins) {
      D.teleport(c.x - C.PLAYER_W / 2, c.y - C.PLAYER_H / 2);
      D.step(C.FIXED_DT);
    }
    const d = D.level.door;
    D.teleport(d.x + 8, d.y + d.h - C.PLAYER_H);
    for (let i = 0; i < 30; i++) D.step(C.FIXED_DT);
    return { state: D.game.state, score: D.game.score, coins: D.game.coins };
  });
  check('reaching the door with all coins wins', winTest.state === 'win', JSON.stringify(winTest));
  check('win awards the escape bonus on top of coins', winTest.score > 300, JSON.stringify(winTest));

  const enemyTest = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    D.loadLevel(33); D.restart();
    const e = D.level.enemies.find(x => x.kind === 'crawler');
    const lives0 = D.game.lives;
    D.teleport(e.x + e.w / 2 - C.PLAYER_W / 2, e.y + e.h / 2 - C.PLAYER_H / 2);
    D.step(C.FIXED_DT); D.step(C.FIXED_DT);
    const afterCrawler = D.game.lives;
    D.player.invuln = 0;
    const w = D.level.enemies.find(x => x.kind === 'wisp');
    D.teleport(w.x + w.w / 2 - C.PLAYER_W / 2, w.y + w.h / 2 - C.PLAYER_H / 2);
    D.step(C.FIXED_DT); D.step(C.FIXED_DT);
    return { lives0, afterCrawler, afterWisp: D.game.lives };
  });
  check('touching the crawler costs a life', enemyTest.afterCrawler === enemyTest.lives0 - 1,
        JSON.stringify(enemyTest));
  check('touching the wisp costs a life', enemyTest.afterWisp === enemyTest.afterCrawler - 1,
        JSON.stringify(enemyTest));

  const enemiesMove = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    D.loadLevel(33); D.restart();
    D.player.invuln = 1e9;   // keep the player out of the way of the test
    const start = D.level.enemies.map(e => ({ x: e.x, y: e.y }));
    let dirFlips = 0;
    const crawler = D.level.enemies.find(e => e.kind === 'crawler');
    let lastDir = crawler.dir, minX = 1e9, maxX = -1e9;
    for (let i = 0; i < 1400; i++) {
      D.step(C.FIXED_DT);
      if (crawler.dir !== lastDir) { dirFlips++; lastDir = crawler.dir; }
      minX = Math.min(minX, crawler.x); maxX = Math.max(maxX, crawler.x);
    }
    const moved = D.level.enemies.map((e, i) =>
      Math.hypot(e.x - start[i].x, e.y - start[i].y) > 4 ||
      (i === 0 && (maxX - minX) > 16));
    // crawler must stay on its ledge
    const seg = D.level.segs.find(s => crawler.x >= s.x * C.TILE - C.TILE && crawler.x < (s.x + s.len) * C.TILE + C.TILE);
    const grounded = crawler.grounded;
    return { moved, dirFlips, span: maxX - minX, grounded, onLedge: !!seg };
  });
  check('both enemies actually move', enemiesMove.moved.every(Boolean), JSON.stringify(enemiesMove));
  check('crawler patrols back and forth without falling off',
        enemiesMove.dirFlips >= 2 && enemiesMove.grounded && enemiesMove.span > 16,
        JSON.stringify(enemiesMove));

  const spikeTest = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    D.loadLevel(33); D.restart();
    // find a spike tile
    let sx = -1, sy = -1;
    for (let y = 0; y < C.MAP_H && sx < 0; y++)
      for (let x = 0; x < C.MAP_W; x++)
        if (D.tileAt(x, y) === 4) { sx = x; sy = y; break; }
    if (sx < 0) return { found: false };
    const lives0 = D.game.lives;
    D.teleport(sx * C.TILE + 6, sy * C.TILE + C.TILE - C.PLAYER_H + 8);
    D.step(C.FIXED_DT); D.step(C.FIXED_DT);
    return { found: true, lives0, after: D.game.lives, respawnedSafe: !D.player.invuln ? false : true };
  });
  check('spikes cost a life', spikeTest.found && spikeTest.after === spikeTest.lives0 - 1,
        JSON.stringify(spikeTest));

  const pitTest = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    D.loadLevel(33); D.restart();
    const lives0 = D.game.lives;
    D.teleport(D.level.spawn.x, C.MAP_H * C.TILE + 300);
    D.step(C.FIXED_DT);
    const after = D.game.lives;
    const backOnMap = D.player.y < C.MAP_H * C.TILE;
    return { lives0, after, backOnMap };
  });
  check('falling out of the world costs a life and respawns on safe ground',
        pitTest.after === pitTest.lives0 - 1 && pitTest.backOnMap, JSON.stringify(pitTest));

  /* ------------------------------------------------------------------ */
  console.log('\n== 7. Lives, game over, restart ==');

  const gameOver = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    D.loadLevel(33); D.restart();
    const seen = [];
    for (let k = 0; k < 4; k++) {
      D.player.invuln = 0;
      const e = D.level.enemies.find(x => x.kind === 'crawler');
      D.teleport(e.x + e.w / 2 - C.PLAYER_W / 2, e.y + e.h / 2 - C.PLAYER_H / 2);
      D.step(C.FIXED_DT); D.step(C.FIXED_DT);
      seen.push({ lives: D.game.lives, state: D.game.state });
      if (D.game.state !== 'playing') break;
    }
    // run out the death animation
    for (let i = 0; i < 200; i++) D.step(C.FIXED_DT);
    return { seen, finalState: D.game.state, lives: D.game.lives };
  });
  check('starts with 3 lives and reaches game over on the 3rd hit',
        gameOver.seen.length === 3 && gameOver.lives === 0, JSON.stringify(gameOver.seen));
  check('game over overlay state is reached', gameOver.finalState === 'gameover', gameOver.finalState);

  const restartTest = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    // From gameover, a keypress must restart.
    const seedBefore = D.game.seed;
    for (let i = 0; i < 100; i++) D.step(C.FIXED_DT);   // pass the input lockout
    D.setKey('jump', true);
    D.step(C.FIXED_DT);
    D.setKey('jump', false);
    return {
      state: D.game.state, lives: D.game.lives, score: D.game.score,
      coins: D.game.coins, sameSeed: D.game.seed === seedBefore
    };
  });
  check('press-to-restart works from the game over screen',
        restartTest.state === 'playing' && restartTest.lives === 3 &&
        restartTest.score === 0 && restartTest.coins === 0, JSON.stringify(restartTest));
  check('restart keeps the same dungeon', restartTest.sameSeed === true, JSON.stringify(restartTest));

  const overlayLockout = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    D.loadLevel(33); D.restart();
    D.game.state = 'gameover'; D.game.overlayTimer = 0;
    D.setKey('jump', true);
    D.step(C.FIXED_DT);
    const immediate = D.game.state;
    D.setKey('jump', false);
    for (let i = 0; i < 90; i++) D.step(C.FIXED_DT);
    D.setKey('jump', true); D.step(C.FIXED_DT); D.setKey('jump', false);
    return { immediate, later: D.game.state };
  });
  check('overlay ignores the keystroke that caused it (no instant dismiss)',
        overlayLockout.immediate === 'gameover' && overlayLockout.later === 'playing',
        JSON.stringify(overlayLockout));

  const newLevelTest = await page.evaluate(() => {
    const D = window.DungeonEscape;
    const before = D.game.seed;
    D.newLevel();
    return { before, after: D.game.seed, changed: D.game.seed !== before, state: D.game.state };
  });
  check('N generates a different dungeon', newLevelTest.changed && newLevelTest.state === 'playing',
        JSON.stringify(newLevelTest));

  /* ------------------------------------------------------------------ */
  console.log('\n== 8. Camera ==');

  const camTest = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    D.loadLevel(55); D.restart();
    const maxX = C.MAP_W * C.TILE - C.VIEW_W, maxY = C.MAP_H * C.TILE - C.VIEW_H;
    let outOfBounds = 0, worstCentre = 0, samples = 0;
    // sweep the player across the whole level and watch the camera
    for (let step = 0; step < 200; step++) {
      const tx = (2 + (step / 200) * (C.MAP_W - 6)) * C.TILE;
      D.teleport(tx, D.level.segs[0].top * C.TILE - C.PLAYER_H);
      for (let i = 0; i < 40; i++) D.step(C.FIXED_DT);
      const cam = D.camera;
      if (cam.x < -0.5 || cam.x > maxX + 0.5 || cam.y < -0.5 || cam.y > maxY + 0.5) outOfBounds++;
      // Away from the level edges the player should be near screen centre.
      const px = D.player.x + C.PLAYER_W / 2 - cam.x;
      if (tx > C.VIEW_W && tx < C.MAP_W * C.TILE - C.VIEW_W) {
        worstCentre = Math.max(worstCentre, Math.abs(px - C.VIEW_W / 2));
        samples++;
      }
    }
    return { outOfBounds, worstCentre, samples, maxX, maxY };
  });
  check('camera never scrolls outside the level', camTest.outOfBounds === 0, JSON.stringify(camTest));
  check('camera keeps the player near screen centre away from edges',
        camTest.samples > 50 && camTest.worstCentre < 130,
        'worst offset from centre = ' + camTest.worstCentre.toFixed(1) + 'px');

  const camSmooth = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    D.loadLevel(55); D.restart();
    D.clearKeys(); D.setKey('right', true);
    let maxJump = 0, prev = D.camera.x;
    for (let i = 0; i < 900; i++) {
      D.step(C.FIXED_DT);
      maxJump = Math.max(maxJump, Math.abs(D.camera.x - prev));
      prev = D.camera.x;
    }
    D.clearKeys();
    return maxJump;
  });
  check('camera motion is smooth (no per-tick teleports)', camSmooth < 6,
        'largest single-tick camera move = ' + camSmooth.toFixed(2) + 'px');

  /* ------------------------------------------------------------------ */
  console.log('\n== 9. One-way platforms ==');

  const oneWay = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    // find a level that has planks
    let plank = null, seed = 0;
    for (let s = 1; s <= 40 && !plank; s++) {
      D.loadLevel(s); D.restart();
      for (let y = 2; y < C.MAP_H && !plank; y++)
        for (let x = 2; x < C.MAP_W; x++)
          if (D.tileAt(x, y) === 3) { plank = { x, y }; seed = s; break; }
    }
    if (!plank) return { found: false };

    // 1. Falling onto a plank from above must land on it.
    D.teleport(plank.x * C.TILE + 6, (plank.y - 4) * C.TILE);
    D.player.vy = 0;
    for (let i = 0; i < 200; i++) { D.step(C.FIXED_DT); if (D.player.grounded) break; }
    const landedOn = D.player.grounded && Math.abs((D.player.y + C.PLAYER_H) - plank.y * C.TILE) < 2;

    // 2. Jumping from underneath must pass straight through.
    D.clearKeys();
    D.teleport(plank.x * C.TILE + 6, (plank.y + 1) * C.TILE + 4);
    D.player.vy = -700;
    let passedThrough = false;
    for (let i = 0; i < 40; i++) {
      D.step(C.FIXED_DT);
      if (D.player.y + C.PLAYER_H < plank.y * C.TILE) passedThrough = true;
    }

    // 3. Down+jump while standing on it must drop through.
    D.clearKeys();
    D.teleport(plank.x * C.TILE + 6, plank.y * C.TILE - C.PLAYER_H);
    for (let i = 0; i < 40; i++) D.step(C.FIXED_DT);
    const standing = D.player.grounded;
    D.setKey('down', true); D.setKey('jump', true);
    for (let i = 0; i < 6; i++) D.step(C.FIXED_DT);
    D.setKey('jump', false);
    for (let i = 0; i < 60; i++) D.step(C.FIXED_DT);
    const droppedThrough = D.player.y + C.PLAYER_H > plank.y * C.TILE + 8;
    D.clearKeys();
    return { found: true, seed, landedOn, passedThrough, standing, droppedThrough };
  });
  check('one-way plank catches a fall from above', oneWay.found && oneWay.landedOn, JSON.stringify(oneWay));
  check('one-way plank can be jumped through from below', oneWay.passedThrough, JSON.stringify(oneWay));
  check('down + jump drops through a plank', oneWay.standing && oneWay.droppedThrough, JSON.stringify(oneWay));

  // Regression: after stepping off a plank onto solid rock, the "I am on a
  // one-way" flag must clear, or down+jump would silently eat the jump.
  const plankFlag = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    let plank = null;
    for (let s = 1; s <= 40 && !plank; s++) {
      D.loadLevel(s); D.restart();
      for (let y = 2; y < C.MAP_H && !plank; y++)
        for (let x = 2; x < C.MAP_W; x++)
          if (D.tileAt(x, y) === 3) { plank = { x, y }; break; }
    }
    if (!plank) return { found: false };
    // Land on the plank...
    D.clearKeys();
    D.teleport(plank.x * C.TILE + 6, (plank.y - 3) * C.TILE);
    D.player.invuln = 1e9;
    for (let i = 0; i < 200; i++) { D.step(C.FIXED_DT); if (D.player.grounded) break; }
    const onPlank = D.player.groundOneWay;
    // ...then move to the solid ledge below and stand on it.
    const seg = D.level.segs.find(s => plank.x >= s.x && plank.x < s.x + s.len);
    D.teleport(plank.x * C.TILE + 6, seg.top * C.TILE - C.PLAYER_H);
    for (let i = 0; i < 30; i++) { D.player.invuln = 1e9; D.step(C.FIXED_DT); }
    const onRock = D.player.groundOneWay;
    // down+jump on solid rock must still be a normal jump.
    D.setKey('down', true); D.setKey('jump', true);
    D.step(C.FIXED_DT);
    const vy = D.player.vy;
    D.clearKeys();
    return { found: true, onPlank, onRock, vy, jumped: vy < -C.JUMP_VEL * 0.7 };
  });
  check('plank flag clears when stepping onto solid rock',
        plankFlag.found && plankFlag.onPlank === true && plankFlag.onRock === false,
        JSON.stringify(plankFlag));
  check('down + jump on solid ground still jumps normally', plankFlag.jumped === true,
        JSON.stringify(plankFlag));

  /* ------------------------------------------------------------------ */
  console.log('\n== 10. Self-containment & rendering ==');

  const selfContained = await page.evaluate(() => {
    const html = document.documentElement.outerHTML;
    return {
      externalScripts: Array.from(document.querySelectorAll('script[src]')).map(s => s.src),
      externalLinks: Array.from(document.querySelectorAll('link[href]')).map(s => s.href),
      images: Array.from(document.querySelectorAll('img')).length,
      hasHttp: /(?:src|href)\s*=\s*["']https?:/i.test(html)
    };
  });
  check('no external scripts', selfContained.externalScripts.length === 0, JSON.stringify(selfContained.externalScripts));
  check('no external stylesheets or link tags', selfContained.externalLinks.length === 0, JSON.stringify(selfContained.externalLinks));
  check('no <img> assets', selfContained.images === 0);
  check('no http(s) asset references anywhere in the document', selfContained.hasHttp === false);

  const netRequests = [];
  page.on('request', r => { if (!r.url().startsWith('file://') && !r.url().startsWith('data:')) netRequests.push(r.url()); });
  await page.evaluate(() => { window.DungeonEscape.resumeLoop(); });
  await page.waitForTimeout(1200);
  check('makes zero network requests while running', netRequests.length === 0, netRequests.join(', '));

  // Real rendering: the canvas must not be blank, and it must change over time.
  const renderCheck = await page.evaluate(async () => {
    const D = window.DungeonEscape;
    D.loadLevel(77); D.restart();
    const cv = document.getElementById('game');
    function snapshot() {
      const t = document.createElement('canvas');
      t.width = 120; t.height = 80;
      const g = t.getContext('2d');
      g.drawImage(cv, 0, 0, 120, 80);
      return g.getImageData(0, 0, 120, 80).data;
    }
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    const a = snapshot();
    let nonBlack = 0;
    for (let i = 0; i < a.length; i += 4) if (a[i] + a[i + 1] + a[i + 2] > 40) nonBlack++;
    D.setKey('right', true);
    await new Promise(r => setTimeout(r, 400));
    D.setKey('right', false);
    const b = snapshot();
    let diff = 0;
    for (let i = 0; i < a.length; i += 4) if (Math.abs(a[i] - b[i]) > 6) diff++;
    return { nonBlack, total: a.length / 4, diff, w: cv.width, h: cv.height };
  });
  check('canvas renders actual content (not blank)',
        renderCheck.nonBlack > renderCheck.total * 0.25,
        renderCheck.nonBlack + '/' + renderCheck.total + ' lit pixels');
  check('scene animates as the player moves', renderCheck.diff > 100, 'changed pixels=' + renderCheck.diff);
  check('canvas backing store is HiDPI aware', renderCheck.w >= 960, JSON.stringify(renderCheck));

  const overlayRender = await page.evaluate(async () => {
    const D = window.DungeonEscape;
    const cv = document.getElementById('game');
    function lit() {
      const t = document.createElement('canvas'); t.width = 160; t.height = 110;
      const g = t.getContext('2d'); g.drawImage(cv, 0, 0, 160, 110);
      const d = g.getImageData(0, 0, 160, 110).data;
      let n = 0; for (let i = 0; i < d.length; i += 4) if (d[i] + d[i + 1] + d[i + 2] > 250) n++;
      return n;
    }
    const out = {};
    D.game.state = 'win'; D.game.overlayTimer = 1.5;
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    out.win = lit();
    D.game.state = 'gameover'; D.game.overlayTimer = 1.5;
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    out.gameover = lit();
    D.game.state = 'title'; D.game.overlayTimer = 1.5;
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    out.title = lit();
    return out;
  });
  check('win / game over / title overlays all draw', overlayRender.win > 30 &&
        overlayRender.gameover > 30 && overlayRender.title > 30, JSON.stringify(overlayRender));

  /* ------------------------------------------------------------------ */
  console.log('\n== 11. Long soak (stability) ==');
  const soak = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    D.pauseLoop();
    D.loadLevel(99); D.restart();
    let rngState = 999;
    const rnd = () => (rngState = (rngState * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
    let ticks = 0, restarts = 0;
    for (let t = 0; t < 60000; t++) {          // ~8 minutes of gameplay
      if (t % 9 === 0) { D.setKey('left', rnd() < 0.3); D.setKey('right', rnd() < 0.5); D.setKey('down', rnd() < 0.1); }
      if (t % 6 === 0) D.setKey('jump', rnd() < 0.5);
      D.step(C.FIXED_DT);
      ticks++;
      if (D.game.state !== 'playing') {
        for (let k = 0; k < 100; k++) D.step(C.FIXED_DT);
        D.restart(); restarts++;
      }
    }
    D.clearKeys();
    const p = D.player;
    return {
      ticks, restarts,
      particles: D.particles.length,
      finite: isFinite(p.x) && isFinite(p.y) && isFinite(p.vx) && isFinite(p.vy),
      inBounds: p.x > -C.TILE && p.x < C.MAP_W * C.TILE && p.y < C.MAP_H * C.TILE + 400,
      lives: D.game.lives, score: D.game.score, state: D.game.state
    };
  });
  check('60k-tick soak keeps player state finite', soak.finite, JSON.stringify(soak));
  check('60k-tick soak keeps the player inside the world', soak.inBounds, JSON.stringify(soak));
  check('particle pool stays bounded', soak.particles <= 600, 'particles=' + soak.particles);
  check('no errors during the soak', errors.length === 0, errors.slice(0, 3).join(' | '));

  /* ------------------------------------------------------------------ */
  console.log('\n== 12. End-to-end: a bot plays a full dungeon ==');

  const playthrough = await page.evaluate(() => {
    const D = window.DungeonEscape, C = D.config;
    // A dumb but honest bot: walk right, jump at ledge edges and under coins.
    // It only uses inputs a human has (no teleporting), so finishing proves the
    // generated dungeon is genuinely completable end to end.
    // Is there footing ahead in the direction we are walking, at foot level OR
    // within a safe drop below it? Scanning downward matters: at the end of a
    // one-way plank the ledge is still there three tiles down, so the right
    // move is to walk off and drop onto it, not to jump and sail past it.
    function ledgeAhead(p, dir) {
      const probeX = dir > 0 ? p.x + p.w + 10 : p.x - 10;
      const col = Math.floor(probeX / C.TILE);
      const footRow = Math.floor((p.y + p.h + 4) / C.TILE);
      for (let r = footRow; r <= footRow + 4; r++) {
        const t = D.tileAt(col, r);
        if (t === 4) return false;             // spikes: not footing
        if (D.isSolid(t) || t === 3) return true;
      }
      return false;
    }

    function play(seed) {
      D.loadLevel(seed); D.restart(); D.clearKeys();
      const L = D.level;
      let holdJump = 0, backUp = 0, ticks = 0, deaths = 0;
      let segIdx = 0, segSince = 0, bestX = 0;

      while (ticks++ < 120 * 240) {   // 4 minutes of game time, max
        const p = D.player;
        // Infinite lives: a missed jump should cost a retry, not end the probe.
        // Damage and the respawn-to-safe-ground path still run normally.
        D.game.lives = 99;

        // Which ledge are we over?
        const col = Math.floor((p.x + p.w / 2) / C.TILE);
        let idx = segIdx;
        for (let i = 0; i < L.segs.length; i++) {
          if (col >= L.segs[i].x && col < L.segs[i].x + L.segs[i].len) { idx = i; break; }
        }
        if (idx !== segIdx) { segIdx = idx; segSince = 0; } else { segSince++; }
        const seg = L.segs[segIdx];
        const edge = (seg.x + seg.len) * C.TILE;

        // Stalled on this ledge? Back up to buy a longer run-up, then retry.
        if (segSince > 120 * 5 && p.grounded && backUp <= 0 && holdJump <= 0) {
          backUp = 40; segSince = 0;
        }

        // Goal: nearest uncollected coin, else the escape door. The door will
        // not open without all three, so coins come first.
        const missing = L.coins.filter(c => !c.taken);
        const cx = p.x + p.w / 2;
        let goal;
        if (missing.length) {
          goal = missing.reduce((a, b) => Math.abs(a.x - cx) < Math.abs(b.x - cx) ? a : b);
        } else {
          goal = { x: L.door.x + L.door.w / 2, y: L.door.y };
        }
        let dir = goal.x > cx ? 1 : -1;
        if (backUp > 0) { backUp--; dir = -dir; }

        D.setKey('right', dir > 0);
        D.setKey('left', dir < 0);

        if (holdJump > 0) { holdJump--; }
        else {
          D.setKey('jump', false);
          if (p.grounded) {
            // Jump when the ground runs out ahead of us...
            const atEdge = !ledgeAhead(p, dir);
            // ...or when the goal is above and we are underneath it.
            const underGoal = goal.y < p.y - 20 && Math.abs(goal.x - cx) < 48;
            if (atEdge || underGoal) { D.setKey('jump', true); holdJump = 45; }
          }
        }

        const livesBefore = D.game.lives;
        D.step(C.FIXED_DT);
        if (D.game.lives < livesBefore) { deaths++; holdJump = 0; backUp = 0; segSince = 0; }
        bestX = Math.max(bestX, p.x);

        if (D.game.state === 'win') {
          D.clearKeys();
          return { seed, won: true, ticks, deaths, coins: D.game.coins, score: D.game.score,
                   seconds: +(ticks / 120).toFixed(1) };
        }
        if (D.game.state !== 'playing') { D.game.lives = 99; D.game.state = 'playing'; }
      }
      D.clearKeys();
      const p = D.player;
      return { seed, won: false, ticks, deaths, coins: D.game.coins, state: D.game.state,
               x: Math.round(p.x), bestX: Math.round(bestX), doorX: Math.round(L.door.x), segIdx,
               segs: L.segs.length, progress: +((bestX / L.door.x) * 100).toFixed(1) };
    }

    const results = [];
    for (let s = 1; s <= 20; s++) results.push(play(s));
    return results;
  });

  const won = playthrough.filter(r => r.won);
  const lost = playthrough.filter(r => !r.won);
  console.log('    won: ' + won.map(r => 's' + r.seed + ' ' + r.seconds + 's ' + r.deaths + 'd ' + r.score + 'pts').join('  '));
  check('a bot completes every one of 20 procedurally generated dungeons',
        lost.length === 0, JSON.stringify(lost.slice(0, 3)));
  check('bot collects all 3 coins on every run',
        won.length > 0 && won.every(r => r.coins === 3),
        JSON.stringify(won.map(r => r.seed + ':' + r.coins)));

  await browser.close();

  console.log('\n' + '='.repeat(64));
  console.log('  ' + pass + ' passed, ' + fail + ' failed');
  if (fail) { console.log('\nFailures:'); failures.forEach(f => console.log('  - ' + f)); }
  console.log('='.repeat(64) + '\n');
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
