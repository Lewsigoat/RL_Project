# Econ Trainer

A local study app for economics definitions. You enable chapters one by one; locked chapters stay out of flashcards, quizzes, and the glossary.

The same app runs in a browser during development and as a double-clickable desktop app on macOS and Windows. Both modes work offline after the files are on your machine. Progress is stored in `localStorage` (the Electron window has its own store, separate from Safari/Chrome).

## Run in a browser

```bash
cd econ-trainer
npm install
npm run dev
```

Then open the printed local URL (usually `http://localhost:5173`). Routes use a hash (`/#/study`, `/#/quiz`, …) so the packaged desktop app can load from `file://`.

```bash
npm test      # unit tests
npm run build # production web build
npm run preview
```

## Desktop app (Mac and Windows)

### Develop in an Electron window

```bash
cd econ-trainer
npm install
npm run electron:dev
```

This starts the Vite dev server and opens **Econ Trainer** against it. Reload and React Fast Refresh work the same as `npm run dev`.

### Build installers

Installers land in `econ-trainer/release/` and are **not** committed to git.

| Command | What you get |
| --- | --- |
| `npm run dist:mac` | macOS `.dmg` and `.zip` |
| `npm run dist:win` | Windows NSIS `.exe` installer |
| `npm run dist` | Installer for the OS you are building on |
| `npm run dist:dir` | Unpacked app folder (useful for a quick smoke test) |

**macOS**

1. Run `npm run dist:mac` on a Mac (electron-builder cannot produce a reliable `.dmg` from Linux).
2. Open `release/Econ Trainer-<version>-mac.dmg` and drag **Econ Trainer** into Applications.
3. Double-click the app. It works offline.

Unsigned local builds are expected. macOS Gatekeeper may block the first open:

- Right-click the app → **Open** → **Open**, or
- System Settings → Privacy & Security → Open Anyway

A signed, notarized Mac app needs an Apple Developer certificate. You do not need that just to run a build you made yourself.

**Windows**

1. Run `npm run dist:win` on Windows (or on Linux/macOS; electron-builder can cross-compile the NSIS installer).
2. Run `release/Econ Trainer-Setup-<version>.exe`.
3. Keep the desktop or Start Menu shortcut. The installed app works offline.

Windows SmartScreen may warn on an unsigned installer; choose **More info** → **Run anyway** for a build you created.

### Requirements to build

- Node.js 20+ and npm
- `npm install` inside `econ-trainer/`
- Mac `.dmg`: build on macOS
- Windows `.exe`: build on Windows, or use electron-builder’s Windows target from another OS

## How to study

1. On **Chapters**, turn on Chapter 1 only.
2. Open **Study**. Space flips a card; `1`–`4` rate Again / Hard / Good / Easy.
3. Spaced repetition (SM-2) schedules the next review. New cards are capped each day.
4. Use **Quiz** for multiple choice, type-the-term, or self-graded explain-it.
5. Enable the next chapter when you want those terms in the queue.

Export a backup from the Progress page if you switch machines or browsers.

## Add your own definitions

The built-in bank ships in `src/data/`. To use your course wording instead (or as well):

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
