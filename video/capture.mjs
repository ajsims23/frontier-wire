// Records the bulletin: node capture.mjs <timeline.json> <width> <height> <frames> <outdir> [workers] [chrome path]
// Loads engine.html in headless Chrome at width x height and, for every frame, seeks the engine to frame/fps and
// saves outdir/NNNNN.jpg. Frames are split between several browser pages working in parallel (each frame is
// computed from the playhead alone, so the order they're drawn in doesn't matter). ffmpeg encodes the folder.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const here = path.dirname(fileURLToPath(import.meta.url));
const [tlPath, w, h, framesArg, outDir, workersArg, chromeArg] = process.argv.slice(2);
const tl = JSON.parse(fs.readFileSync(tlPath, "utf8"));
const world = JSON.parse(fs.readFileSync(path.join(here, "..", "agent", "assets", "world.json"), "utf8"));
const frames = +framesArg, workers = Math.max(1, Math.min(+workersArg || 1, 8));
fs.mkdirSync(outDir, { recursive: true });
const browser = await puppeteer.launch({
  executablePath: chromeArg || process.env.CHROME_PATH || "/usr/bin/google-chrome",
  headless: true,
  protocolTimeout: 120000,
  args: ["--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files", "--force-color-profile=srgb",
         "--font-render-hinting=none", "--disable-dev-shm-usage", "--mute-audio"],
});
let failed = null, done = 0;
const t0 = Date.now();
async function work(k) {
  const page = await browser.newPage();
  page.on("pageerror", (e) => { failed = failed || `engine error: ${e.message}`; });
  page.on("console", (m) => { if (m.type() === "error") console.error("engine console:", m.text()); });
  await page.setViewport({ width: +w, height: +h, deviceScaleFactor: 1 });
  await page.goto("file://" + path.join(here, "engine.html"), { waitUntil: "load" });
  await page.evaluate((t, wd) => window.init(t, wd), tl, world);
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => window.layout());
  const cdp = await page.createCDPSession();
  for (let f = k; f < frames && !failed; f += workers) {  // interleaved, so every worker gets an even mix of scenes
    await page.evaluate(async (t) => { await window.seek(t); }, f / tl.fps);
    const { data } = await cdp.send("Page.captureScreenshot", { format: "jpeg", quality: 92, optimizeForSpeed: true });
    fs.writeFileSync(path.join(outDir, String(f).padStart(5, "0") + ".jpg"), Buffer.from(data, "base64"));
    if (++done % 500 === 0) console.error(`${w}x${h}: ${done}/${frames} frames (${((Date.now() - t0) / 1000).toFixed(0)}s)`);
  }
  await page.close();
}
try {
  await Promise.all(Array.from({ length: workers }, (_, k) => work(k)));
} catch (e) {
  failed = failed || String(e);
} finally {
  await browser.close();
}
if (failed) { console.error(failed); process.exit(1); }
console.error(`${w}x${h}: ${frames} frames in ${((Date.now() - t0) / 1000).toFixed(0)}s with ${workers} workers`);
