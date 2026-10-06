#!/usr/bin/env node
// Screenshot an HTML file via headless Chromium CDP.
// Usage: node shot.js <input.html> <output.png> [width] [height]
const { spawn: spawnProc } = require("child_process");
const fs = require("fs");
const http = require("http");
const path = require("path");
const WebSocket = require("ws");

const CHROME = "/opt/meta-chromium/chrome";

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function getJson(port, p) {
  return new Promise((resolve, reject) => {
    http.get({ port, path: p }, res => {
      let d = "";
      res.on("data", c => d += c);
      res.on("end", () => { try { resolve(JSON.parse(d)); } catch (e) { reject(e); } });
    }).on("error", reject);
  });
}

async function main() {
  const [html, out, W = "1536", H = "1024"] = process.argv.slice(2);
  if (!html || !out) { console.error("usage: shot.js <in.html> <out.png> [w] [h]"); process.exit(2); }
  const width = parseInt(W, 10), height = parseInt(H, 10);
  const port = 19222 + Math.floor(Math.random() * 2000);

  const chrome = spawnProc(CHROME, [
    "--headless", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage",
    `--remote-debugging-port=${port}`, "--remote-allow-origins=*", "about:blank",
  ], { stdio: "ignore" });

  const fileUrl = "file://" + path.resolve(html);
  let wsUrl = null;
  for (let i = 0; i < 60; i++) {
    try {
      const targets = await getJson(port, "/json/list");
      const page = targets.find(t => t.type === "page");
      if (page && page.webSocketDebuggerUrl) { wsUrl = page.webSocketDebuggerUrl; break; }
    } catch (e) { /* not up yet */ }
    await sleep(500);
  }
  if (!wsUrl) { chrome.kill(); throw new Error("CDP not ready"); }

  const ws = new WebSocket(wsUrl, { maxPayload: 256 * 1024 * 1024 });
  await new Promise((res, rej) => { ws.on("open", res); ws.on("error", rej); });

  let id = 0;
  const pending = new Map();
  ws.on("message", raw => {
    const msg = JSON.parse(raw.toString());
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
    } else if (msg.method === "Page.loadEventFired" && pending.has("load")) {
      pending.get("load").resolve(); pending.delete("load");
    }
  });
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const mid = ++id; pending.set(mid, { resolve, reject });
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
  const waitLoad = () => new Promise(resolve => pending.set("load", { resolve }));

  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 2, mobile: false });
  const loadP = waitLoad();
  await send("Page.navigate", { url: fileUrl });
  await Promise.race([loadP, sleep(15000)]);
  await sleep(1200); // let fonts/layout settle
  const { data } = await send("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync(out, Buffer.from(data, "base64"));
  ws.close();
  chrome.kill();
  console.log("saved", out);
}

main().catch(e => { console.error("shot failed:", e.message); process.exit(1); });
