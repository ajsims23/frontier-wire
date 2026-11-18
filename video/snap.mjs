// Debug helper: node snap.mjs <timeline.json> <w> <h> <outdir> <t1> [t2 ...]  -> PNG frames at those times
import fs from "node:fs"; import path from "node:path"; import { fileURLToPath } from "node:url"; import puppeteer from "puppeteer-core";
const here = path.dirname(fileURLToPath(import.meta.url));
const [tlPath, w, h, out, ...ts] = process.argv.slice(2);
const tl = JSON.parse(fs.readFileSync(tlPath, "utf8"));
const world = JSON.parse(fs.readFileSync(path.join(here, "..", "agent", "assets", "world.json"), "utf8"));
const b = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome", headless: true,
  protocolTimeout: 120000, args: ["--no-sandbox", "--disable-gpu", "--allow-file-access-from-files", "--hide-scrollbars"] });
const p = await b.newPage(); p.on("pageerror", (e) => console.error("ERR", e.message)); p.on("console", (m) => console.error("console", m.text()));
await p.setViewport({ width: +w, height: +h }); await p.goto("file://" + path.join(here, "engine.html"));
await p.evaluate((t, wd) => window.init(t, wd), tl, world); await p.evaluate(() => document.fonts.ready); await p.evaluate(() => window.layout());
for (const t of ts) { await p.evaluate(async (x) => { await window.seek(x); }, +t); await p.screenshot({ path: path.join(out, `f_${w}x${h}_${t}.png`) }); }
await b.close();
