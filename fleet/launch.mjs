#!/usr/bin/env node
// Launch one fleet profile and keep the per-profile noise installed on every
// tab, including tabs opened after launch.
//
//   node launch.mjs --profile <dir> [--proxy socks5://host:port] [--port 0]
//
// The engine is the patched 152 build; the identity file carries the persona
// overrides; the noise shim is injected through Target.setAutoAttach so it
// lands on documents created later as well as the first one.

import { spawn } from "node:child_process";
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { createHash } from "node:crypto";
import net from "node:net";

const args = new Map();
for (let i = 2; i < process.argv.length; i += 2) args.set(process.argv[i].replace(/^--/, ""), process.argv[i + 1]);

const profileDir = args.get("profile") ? resolve(args.get("profile")) : "";
if (!profileDir) {
  console.error("usage: node launch.mjs --profile <dir> [--proxy URL] [--port N]");
  process.exit(2);
}

const metadataPath = join(profileDir, "metadata.json");
const metadata = JSON.parse(readFileSync(metadataPath, "utf8"));
const config = metadata.wayfern_config || {};
const overrides = typeof config.identity_overrides === "string"
  ? JSON.parse(config.identity_overrides)
  : (config.identity_overrides || {});
const location = typeof config.location === "string" ? JSON.parse(config.location) : (config.location || {});
const identityId = config.identity_id || metadata.id;

const engineApp = process.env.WAYFERN_APP
  || `${process.env.HOME}/Library/Application Support/DonutBrowserLocalRuntime/data/binaries/wayfern/152.0.7977.64/Wayfern.app`;
const engine = `${engineApp}/Contents/MacOS/Wayfern`;

const userDataDir = join(profileDir, "profile");
mkdirSync(userDataDir, { recursive: true });

const identityDoc = {
  identityId,
  operatingSystem: config.os || "macos",
  timezone: location.timezone || "America/Denver",
  language: location.language || "en-US",
  ...(typeof location.latitude === "number" ? { latitude: location.latitude } : {}),
  ...(typeof location.longitude === "number" ? { longitude: location.longitude } : {}),
  overrides,
};
const identityFile = join(userDataDir, "wayfern-identity.json");
writeFileSync(identityFile, JSON.stringify(identityDoc));

function freePort() {
  return new Promise((resolve) => {
    const srv = net.createServer();
    srv.listen(0, "127.0.0.1", () => {
      const p = srv.address().port;
      srv.close(() => resolve(p));
    });
  });
}

const debugPort = args.get("port") ? Number(args.get("port")) : await freePort();
const proxy = args.get("proxy") || process.env.WAYFERN_PROXY || metadata.proxy_url || "";

const engineArgs = [
  `--user-data-dir=${userDataDir}`,
  `--remote-debugging-port=${debugPort}`,
  "--remote-debugging-address=127.0.0.1",
  "--no-first-run",
  "--no-default-browser-check",
  "--disable-background-mode",
  "--disable-component-update",
  "--disable-updater",
  "--hide-crash-restore-bubble",
  "--use-mock-keychain",
  "--password-store=basic",
  `--window-size=${config.screen_max_width || overrides.screenWidth || 1440},${config.screen_max_height || overrides.screenHeight || 900}`,
  "--window-position=0,30",
  `--wayfern-identity-file=${identityFile}`,
  "--wayfern-webrtc-mode=auto",
  "--disable-features=DialMediaRouteProvider,DnsOverHttps,AsyncDns,Prefetch,PrefetchProxy,SpeculationRulesPrefetchFuture,NoStatePrefetch",
];
if (proxy) engineArgs.unshift(`--proxy-server=${proxy}`);

const child = spawn(engine, engineArgs, {
  stdio: ["ignore", "ignore", "pipe"],
  env: {
    ...process.env,
    DONUT_FONT_POLICY: "latin-only",
    DYLD_INSERT_LIBRARIES: `${engineApp}/Contents/Frameworks/Wayfern Framework.framework/Versions/152.0.7977.64/DonutFontPolicy.dylib`,
  },
});
child.on("exit", (code, signal) => {
  console.error(`engine exited code=${code} signal=${signal}`);
  process.exit(0);
});
child.stderr.on("data", (buf) => {
  for (const line of buf.toString().split("\n")) {
    if (/dropping|applied before the first navigation|identity/i.test(line)) console.error(line.trim().slice(0, 200));
  }
});

// ---- per-profile noise -------------------------------------------------
const seed = parseInt(createHash("sha256").update(String(identityId)).digest("hex").slice(0, 8), 16) >>> 0;
const shim = `(() => {
  if (window.__donutNoise) { return; }
  Object.defineProperty(window, "__donutNoise", { value: true });
  const SEED = ${seed} >>> 0;
  const pick = (n, salt) => { let x = (SEED ^ salt) >>> 0; x = Math.imul(x ^ (x >>> 15), 2246822507) >>> 0; return n > 0 ? x % n : 0; };
  const proto = HTMLCanvasElement.prototype;
  const origToDataURL = proto.toDataURL;
  proto.toDataURL = function (...a) {
    try {
      const w = this.width, h = this.height;
      if (w > 0 && h > 0 && w * h <= 4000000) {
        const copy = document.createElement("canvas");
        copy.width = w; copy.height = h;
        const ctx = copy.getContext("2d");
        ctx.drawImage(this, 0, 0);
        const alpha = 1 + ((SEED >>> 8) % 64);
        ctx.fillStyle = "rgba(0,0,0," + (alpha / 255) + ")";
        ctx.fillRect(pick(w, 0x9e3779b9), pick(h, 0x85ebca6b), 1, 1);
        ctx.fillStyle = "rgba(0,0,0," + (((alpha * 3) % 200) + 1) / 255 + ")";
        ctx.fillRect(pick(w, 0xc2b2ae35), pick(h, 0x27d4eb2f), 1, 1);
        return origToDataURL.apply(copy, a);
      }
    } catch (e) {}
    return origToDataURL.apply(this, a);
  };
  const ctx2d = CanvasRenderingContext2D.prototype;
  const origGet = ctx2d.getImageData;
  ctx2d.getImageData = function (...a) {
    const out = origGet.apply(this, a);
    try {
      const d = out.data, mark = SEED % 4093;
      for (let i = 0; i < d.length; i += 4) {
        const px = i >>> 2;
        if (((Math.imul(px, 2654435761) >>> 0) % 4093) === mark) { d[i] = d[i] ^ 1; }
      }
    } catch (e) {}
    return out;
  };
  const patchGL = (Ctor) => {
    if (!Ctor || !Ctor.prototype || !Ctor.prototype.readPixels) { return; }
    const orig = Ctor.prototype.readPixels;
    Ctor.prototype.readPixels = function (...a) {
      const r = orig.apply(this, a);
      try { const buf = a[6]; if (buf && buf.length) { const i = pick(buf.length, 0xc2b2ae35); buf[i] = (buf[i] ^ 1) & 255; } } catch (e) {}
      return r;
    };
  };
  patchGL(window.WebGLRenderingContext);
  patchGL(window.WebGL2RenderingContext);
  const OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
  if (OAC && OAC.prototype.startRendering) {
    const origRender = OAC.prototype.startRendering;
    OAC.prototype.startRendering = function () {
      return origRender.apply(this, arguments).then((buffer) => {
        try {
          const d = buffer.getChannelData(0);
          const delta = ((SEED % 100000) + 1) * 1e-9;
          for (let i = 0; i < d.length; i += 97) { d[i] = d[i] + delta; }
        } catch (e) {}
        return buffer;
      });
    };
  }
})();`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function browserWs() {
  for (let i = 0; i < 60; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${debugPort}/json/version`);
      if (res.ok) {
        const info = await res.json();
        if (info.webSocketDebuggerUrl) return info.webSocketDebuggerUrl;
      }
    } catch {}
    await sleep(250);
  }
  throw new Error("cdp not ready");
}

const ws = new WebSocket(await browserWs());
let nextId = 0;
const pending = new Map();
const sessions = new Set();

ws.addEventListener("message", async (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    pending.get(msg.id)(msg);
    pending.delete(msg.id);
    return;
  }
  if (msg.method === "Target.attachedToTarget") {
    const { sessionId, targetInfo, waitingForDebugger } = msg.params;
    if (targetInfo.type === "page") {
      sessions.add(sessionId);
      await call("Page.addScriptToEvaluateOnNewDocument", { source: shim, runImmediately: true }, sessionId);
      await call("Page.enable", {}, sessionId).catch(() => {});
      if (waitingForDebugger) await call("Runtime.runIfWaitingForDebugger", {}, sessionId).catch(() => {});
      console.error(`noise installed session=${sessionId.slice(0, 8)} url=${String(targetInfo.url).slice(0, 60)}`);
    } else if (waitingForDebugger) {
      await call("Runtime.runIfWaitingForDebugger", {}, sessionId).catch(() => {});
    }
  }
});

function call(method, params = {}, sessionId) {
  const id = ++nextId;
  const payload = { id, method, params };
  if (sessionId) payload.sessionId = sessionId;
  return new Promise((resolve) => {
    pending.set(id, resolve);
    ws.send(JSON.stringify(payload));
  });
}

await new Promise((r) => ws.addEventListener("open", r));
await call("Target.setDiscoverTargets", { discover: true });
await call("Target.setAutoAttach", { autoAttach: true, waitForDebuggerOnStart: true, flatten: true });

// Open the start page in a fresh tab so the shim is exercised from the start.
await call("Target.createTarget", { url: "about:blank" });
await sleep(800);

console.log(JSON.stringify({ profile: metadata.id, name: metadata.name, port: debugPort, seed, pid: child.pid }));
