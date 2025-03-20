#!/usr/bin/env node
/**
 * Render the Mermaid diagrams to SVG (and optionally PNG).
 *
 * Usage:
 *   node scripts/render_diagrams.mjs
 *   node scripts/render_diagrams.mjs --png
 *
 * Needs the frontend dev dependencies (mermaid + playwright):
 *   cd frontend && npm install
 */
import { readFile, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { dirname, extname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const require = createRequire(resolve(root, "frontend", "package.json"));

let mermaidDir;
let chromium;
try {
  mermaidDir = dirname(require.resolve("mermaid/dist/mermaid.esm.mjs"));
  ({ chromium } = require("playwright"));
} catch (error) {
  console.error("This script needs the frontend dev dependencies:");
  console.error("  cd frontend && npm install");
  console.error(`(original error: ${error.message})`);
  process.exit(1);
}

const diagrams = ["architecture", "evaluation-lifecycle"];
const wantPng = process.argv.includes("--png");

const MIME = {
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".json": "application/json",
  ".css": "text/css",
  ".map": "application/json",
};

const server = createServer(async (request, response) => {
  const url = new URL(request.url, "http://127.0.0.1");

  // Serve the mermaid bundle (and its sibling chunks) from node_modules.
  if (url.pathname.startsWith("/mermaid/")) {
    const relative = url.pathname.replace("/mermaid/", "");
    try {
      const body = await readFile(resolve(mermaidDir, relative));
      response.writeHead(200, {
        "content-type": MIME[extname(relative)] || "application/octet-stream",
        "cache-control": "no-store",
      });
      response.end(body);
      return;
    } catch {
      response.writeHead(404);
      response.end("not found");
      return;
    }
  }

  const name = url.pathname.replace(/^\//, "");
  if (!diagrams.includes(name)) {
    response.writeHead(404);
    response.end("not found");
    return;
  }
  const source = await readFile(resolve(root, "docs", "diagrams", `${name}.mmd`), "utf8");
  const html = `<!DOCTYPE html><html><head><meta charset="utf-8">
    <style>
      body{margin:0;background:#ffffff;font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
      #diagram{display:inline-block;padding:28px}
      .nodeLabel, .edgeLabel, text, .label { font-family: system-ui, -apple-system, "Segoe UI", sans-serif !important; }
    </style></head>
    <body><div id="diagram"><pre class="mermaid">${source
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")}</pre></div>
    <script type="module">
      import mermaid from '/mermaid/mermaid.esm.mjs';
      mermaid.initialize({ startOnLoad: false, theme: 'default', securityLevel: 'loose',
                           flowchart: { htmlLabels: true } });
      try {
        await mermaid.run({ querySelector: '.mermaid' });
        window.__mermaidDone = true;
      } catch (error) {
        window.__mermaidError = String(error && error.message || error);
        window.__mermaidDone = true;
      }
    </script></body></html>`;
  response.writeHead(200, { "content-type": "text/html; charset=utf-8" });
  response.end(html);
});

await new Promise((resolveListen) => server.listen(0, "127.0.0.1", resolveListen));
const port = server.address().port;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1800, height: 1400 }, deviceScaleFactor: 2 });
page.on("pageerror", (error) => console.error("  [page error]", error.message));

for (const name of diagrams) {
  await page.goto(`http://127.0.0.1:${port}/${name}`);
  await page.waitForFunction(() => window.__mermaidDone === true, null, { timeout: 60000 });
  const error = await page.evaluate(() => window.__mermaidError || null);
  if (error) {
    console.error(`  ! mermaid error for ${name}: ${error}`);
  }
  const svg = await page.$eval("#diagram", (element) => {
    const node = element.querySelector("svg");
    if (!node) return "";
    const clone = node.cloneNode(true);
    clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    clone.setAttribute("xmlns:xlink", "http://www.w3.org/1999/xlink");
    clone.removeAttribute("style");
    const background = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    background.setAttribute("x", "0");
    background.setAttribute("y", "0");
    background.setAttribute("width", "100%");
    background.setAttribute("height", "100%");
    background.setAttribute("fill", "#ffffff");
    clone.insertBefore(background, clone.firstChild);
    return `<?xml version="1.0" encoding="UTF-8"?>\n${clone.outerHTML}`;
  });
  if (!svg.includes("<svg")) {
    console.error(`  ! no SVG produced for ${name}`);
    continue;
  }
  const svgPath = resolve(root, "docs", "diagrams", `${name}.svg`);
  await writeFile(svgPath, svg, "utf8");
  console.log(`wrote ${svgPath}`);

  if (wantPng) {
    const element = await page.$("#diagram");
    const pngPath = resolve(root, "docs", "diagrams", `${name}.png`);
    await element.screenshot({ path: pngPath });
    console.log(`wrote ${pngPath}`);
  }
}

await browser.close();
server.close();
