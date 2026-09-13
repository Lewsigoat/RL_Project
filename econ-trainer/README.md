# Econ Trainer

A local study app for economics definitions. You enable chapters one by one; locked chapters stay out of flashcards, quizzes, and the glossary.

The built-in bank is **Edexcel IGCSE Economics (EC2)** — 42 chapters and 177 terms, worded from the EoY revision workbook and completed answers (not a generic intro/Mankiw list).

**Chapters**

1. The Market System — The Economic Problem
2. The Market System — Economic Assumptions
3. Demand Curve
4. Factors that Shift Demand
5. Supply Curve
6. Factors that Shift Supply
7. Market Equilibrium
8. Price Elasticity of Demand (PED)
9. Price Elasticity of Supply (PES)
10. Income Elasticity of Demand (YED)
11. Mixed Economy & Market Failure
12. Privatisation
13. Externalities
14. Factors of Production & Sectors of the Economy
15. Productivity & Division of Labour
16. Business Costs, Revenue and Profit
17. Economies and Diseconomies of Scale
18. Competitive Markets
19. Large and Small Firms
20. Monopoly
21. Oligopoly
22. The Labour Market — Demand and Supply
23. The Labour Market — Trade Unions
24. Government Intervention
25. Economic Growth
26. Inflation
27. Unemployment
28. Balance of Payments (Current Account)
29. Protection of the Environment
30. Redistribution of Income
31. Fiscal Policy
32. Monetary Policy
33. Supply-Side Policies
34. Relationships Between Objectives and Policies
35. Globalisation
36. Multinational Companies and Foreign Direct Investment
37. International Trade
38. Protectionism
39. Trading Blocs
40. The World Trade Organization and World Trade Patterns
41. Exchange Rates and Their Determination
42. Impact of Changing Exchange Rates

The same app runs in a browser during development and as a double-clickable desktop app on macOS and Windows. Both modes work offline after the files are on your machine. Progress is stored in `localStorage` (the Electron window has its own store, separate from Safari/Chrome).

## How to open it

`http://localhost:5188` is **not** a public website. It only works after you start Econ Trainer **on the same computer** you are using.

### On your Mac (browser)

In Terminal, from the repo:

```bash
cd econ-trainer
npm install
npm run dev
```

Wait until the terminal prints `Local: http://localhost:5188/`. Then open:

**http://localhost:5188**

Leave that Terminal window open. Closing it stops the site.

### On your Mac (desktop window, no URL)

```bash
cd econ-trainer
npm install
npm run electron:dev
```

A window titled **Econ Trainer** opens. You do not type a URL.

### If you do not want Node / npm

Download the Mac app (`Econ-Trainer-mac.dmg` on Apple Silicon, or `Econ-Trainer-mac-intel.zip` on Intel). Open the disk image, drag **Econ Trainer** into Applications, then launch it. See [Install on a Mac](#install-on-a-mac).

### Why “http://localhost:5188 does not load”

1. You opened the URL without running `npm run dev` (or `npm run electron:dev`) on **this Mac**. Nothing is listening until you start it.
2. A Cloud Agent’s `localhost` is a remote Linux VM, not your laptop. Port 5188 on the agent does not appear on your Mac unless you run the commands above **here**, or you use Cursor’s Ports / Preview panel while that agent’s Vite server is running.
3. **http://localhost:5173 is Neon Country** (or another Vite app). Econ Trainer is pinned to **5188** and will exit instead of hopping if that port is taken.

## Install on a Mac

1. Download **Econ-Trainer-mac.dmg** (or **Econ-Trainer-mac.zip**).
2. Open the disk image and drag **Econ Trainer** into **Applications**. If you have the zip, unzip it and drag **Econ Trainer.app** into **Applications**.
3. Open the app from Applications. It works offline.

If Gatekeeper blocks the first launch (this build is unsigned): right-click **Econ Trainer** → **Open** → **Open**. Or System Settings → Privacy & Security → Open Anyway.

The downloadable **Econ-Trainer-mac.dmg** is an Apple Silicon (arm64) build. Intel Macs can rebuild with `npm run dist:mac` (that command also produces an x64 zip).

## Other commands

Routes use a hash (`/#/study`, `/#/quiz`, …) so the packaged desktop app can load from `file://`.

```bash
npm test      # unit tests
npm run build # production web build
npm run preview
```

## Desktop app (Mac and Windows)

`npm run electron:dev` starts Vite on **5188** and opens the desktop window against it (not 5173). Reload and React Fast Refresh work the same as `npm run dev`.

### Build installers

Installers land in `econ-trainer/release/` and are **not** committed to git.

| Command | What you get |
| --- | --- |
| `npm run dist:mac` | macOS `.dmg` and `.zip` |
| `npm run dist:win` | Windows NSIS `.exe` installer |
| `npm run dist` | Installer for the OS you are building on |
| `npm run dist:dir` | Unpacked app folder (useful for a quick smoke test) |

**macOS**

See [Install on a Mac](#install-on-a-mac) if you just want the downloadable app. To rebuild installers:

1. Run `npm run dist:mac` (unsigned `.dmg` + `.zip` for arm64 and Intel).
2. Open the `.dmg` and drag **Econ Trainer** into Applications.

Unsigned local builds are expected. A signed, notarized Mac app needs an Apple Developer certificate.

**Windows**

1. Run `npm run dist:win` on Windows (or on Linux/macOS; electron-builder can cross-compile the NSIS installer).
2. Run `release/Econ Trainer-Setup-<version>.exe`.
3. Keep the desktop or Start Menu shortcut. The installed app works offline.

Windows SmartScreen may warn on an unsigned installer; choose **More info** → **Run anyway** for a build you created.

### Requirements to build

- Node.js 20+ and npm
- `npm install` inside `econ-trainer/`
- Mac `.dmg` / `.zip`: `npm run dist:mac` (unsigned arm64 + Intel; Gatekeeper: right-click → Open)
- Windows `.exe`: build on Windows, or use electron-builder’s Windows target from another OS

## How to study

1. On **Chapters**, turn on Chapter 1 only.
2. Open **Study**. Space flips a card; `1`–`4` rate Again / Hard / Good / Easy.
3. Spaced repetition (SM-2) schedules the next review. New cards are capped each day.
4. Use **Quiz** for multiple choice, type-the-term, or self-graded explain-it.
5. Enable the next chapter when you want those terms in the queue.

Export a backup from the Progress page if you switch machines or browsers.

## Add your own definitions

The built-in bank already uses the EC2 workbook wording in `src/data/`. To add extra terms or override a definition:

1. Copy `public/custom-terms.example.json`.
2. Add chapters and terms. Custom ids replace built-in terms with the same id.
3. Import the file from **Progress → Import term pack**.

A term looks like:

```json
{
  "id": "opportunity-cost",
  "chapterId": "ch1",
  "term": "Opportunity cost",
  "definition": "The value of the next-best alternative.",
  "example": "Optional.",
  "related": ["scarcity"],
  "aliases": ["alt name"]
}
```

You can also regenerate the built-in JSON after editing `scripts/build_definitions.py`:

```bash
python3 scripts/build_definitions.py
```
