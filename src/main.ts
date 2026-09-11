import { Game } from "./core/Game";

const canvas = document.querySelector("#game-canvas");
if (!(canvas instanceof HTMLCanvasElement)) {
  throw new Error("Neon County canvas is missing.");
}

const game = new Game(canvas);
game.start();

window.addEventListener("error", (event) => {
  console.error("[Neon County]", event.error ?? event.message);
});

window.addEventListener("unhandledrejection", (event) => {
  console.error("[Neon County]", event.reason);
});
