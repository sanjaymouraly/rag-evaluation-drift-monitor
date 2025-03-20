#!/usr/bin/env node
/**
 * Capture genuine screenshots of the running dashboard.
 *
 * Prerequisite: the backend (:8000) and the frontend (:5173) are running and
 * the database is seeded (`python -m app.seed --reset`).
 *
 *   node scripts/capture_screenshots.mjs                       # all shots
 *   node scripts/capture_screenshots.mjs --base http://127.0.0.1:5173
 *
 * The script navigates by route, waits for the network to settle and the page
 * to render, and writes PNG files to docs/images/.
 */
import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const require = createRequire(resolve(root, "frontend", "package.json"));

const { chromium } = require("playwright");

const args = process.argv.slice(2);
const baseIndex = args.indexOf("--base");
const BASE = baseIndex >= 0 ? args[baseIndex + 1] : "http://127.0.0.1:5173";
const OUT = resolve(root, "docs", "images");

const SHOTS = [
  { path: "/", name: "01-overview" },
  { path: "/runs", name: "02-runs" },
  { path: "/runs/2", name: "03-run-evidence" },
  { path: "/compare", name: "04-compare" },
  {
    path: "/regressions",
    name: "05-regressions",
    async act(page) {
      // Expand the failing evaluation so the screenshot shows the evidence.
      const button = page.getByRole("button", { name: "Show checks" }).first();
      if (await button.count()) {
        await button.click();
        await page.waitForTimeout(600);
      }
    },
  },
  { path: "/drift", name: "06-drift" },
  { path: "/gates", name: "07-release-gates" },
  { path: "/providers", name: "08-providers" },
  { path: "/datasets", name: "09-datasets" },
  { path: "/metrics", name: "10-metrics" },
  {
    path: "/evidence",
    name: "11-evidence",
    async act(page) {
      // Show the full baseline run and expand one question.
      const select = page.getByLabel("Evaluation run");
      if (await select.count()) {
        await select.selectOption("2");
        await page.waitForTimeout(900);
      }
      const show = page.getByRole("button", { name: "Show" }).first();
      if (await show.count()) {
        await show.click();
        await page.waitForTimeout(600);
      }
    },
  },
  { path: "/reports", name: "12-reports" },
  { path: "/system", name: "13-system" },
  { path: "/runs/new", name: "14-new-evaluation" },
  { path: "/applications", name: "15-applications" },
];

await mkdir(OUT, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 960 }, deviceScaleFactor: 1 });
const page = await context.newPage();
page.on("console", (message) => {
  if (message.type() === "error") console.error("  [browser error]", message.text());
});

for (const shot of SHOTS) {
  const url = `${BASE}${shot.path}`;
  try {
    await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });
  } catch (error) {
    console.warn(`  ! ${shot.path}: ${error.message.split("\n")[0]}`);
  }
  await page.waitForTimeout(900);
  if (shot.act) {
    try {
      await shot.act(page);
    } catch (error) {
      console.warn(`  ! interaction on ${shot.path}: ${error.message.split("\n")[0]}`);
    }
  }
  const file = resolve(OUT, `${shot.name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  console.log(`saved ${file}`);
}

await browser.close();
console.log("done");
