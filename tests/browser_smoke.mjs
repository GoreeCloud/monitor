/** Real browser acceptance for GoreeCloud Monitor's development UI.
 * Only CI-owned loopback services, a disposable SQLite DB and fixture values.
 * Requires Node.js 22+ and an existing Chrome/Chromium executable; no npm packages.
 */
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { createServer } from "node:net";
import { setTimeout as delay } from "node:timers/promises";

const FIXTURE_PASSWORD = "CI-only-browser-fixture-password";
const TARGET_NAME = "CI private push service";
const output = resolve("artifacts/browser-ui");
mkdirSync(output, { recursive: true });

async function freePort() {
  const socket = createServer();
  await new Promise((ok, bad) => socket.once("error", bad).listen(0, "127.0.0.1", ok));
  const port = socket.address().port;
  await new Promise((ok, bad) => socket.close(error => error ? bad(error) : ok()));
  return port;
}
async function waitFor(action, description, maxMs = 15000) {
  const deadline = Date.now() + maxMs;
  let last;
  while (Date.now() < deadline) {
    try {
      const result = await action();
      if (result) return result;
    } catch (error) { last = error; }
    await delay(100);
  }
  throw new Error("Timed out: " + description + (last ? " (" + last.message + ")" : ""));
}
function chromeBinary() {
  if (process.env.CHROME_BIN && existsSync(process.env.CHROME_BIN)) return process.env.CHROME_BIN;
  for (const name of ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
                      "/usr/bin/chromium", "/usr/bin/chromium-browser"]) {
    if (existsSync(name)) return name;
  }
  throw new Error("Chrome or Chromium not installed on the CI runner");
}
async function createTab(debugPort, url) {
  const result = await fetch("http://127.0.0.1:" + debugPort +
    "/json/new?" + encodeURIComponent(url), { method: "PUT" });
  assert.equal(result.status, 200, "Chrome debugging target creation");
  return await result.json();
}
async function openWebSocket(url) {
  return new Promise((ok, bad) => {
    const ws = new WebSocket(url);
    ws.addEventListener("open", () => ok(ws), { once: true });
    ws.addEventListener("error", () => bad(new Error("Chrome WebSocket failed")), { once: true });
  });
}
class Browser {
  constructor(socket) {
    this.socket = socket;
    this.number = 0;
    this.waiters = new Map();
    socket.addEventListener("message", event => {
      let message;
      try { message = JSON.parse(event.data); } catch (_) { return; }
      if (!message.id) return;
      const task = this.waiters.get(message.id);
      if (!task) return;
      clearTimeout(task.timer);
      this.waiters.delete(message.id);
      if (message.error) task.reject(new Error(message.error.message));
      else task.resolve(message.result);
    });
  }
  command(method, params = {}) {
    const id = ++this.number;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.waiters.delete(id);
        reject(new Error("Chrome protocol timeout: " + method));
      }, 10000);
      this.waiters.set(id, {resolve, reject, timer});
      this.socket.send(JSON.stringify({id, method, params}));
    });
  }
  async evaluate(expression) {
    const result = await this.command("Runtime.evaluate", {
      expression, awaitPromise: true, returnByValue: true,
    });
    if (result.exceptionDetails) {
      throw new Error("Browser JS exception: " +
        (result.exceptionDetails.exception?.description || result.exceptionDetails.text || "Unknown page script error"));
    }
    return result.result?.value;
  }
  async screenshot(name) {
    const data = await this.command("Page.captureScreenshot", {
      format: "png", captureBeyondViewport: false,
    });
    writeFileSync(join(output, name + ".png"), Buffer.from(data.data, "base64"));
  }
  close() {
    this.socket.close();
  }
}
async function checkViewport(browser, name, width, height, mobile) {
  await browser.command("Emulation.setDeviceMetricsOverride", {
    width, height, deviceScaleFactor: 1, mobile,
  });
  await delay(200);
  const dimensions = await browser.evaluate(`({
    innerWidth: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    visible: document.querySelector("#workspace")?.hidden === false,
  })`);
  assert.equal(dimensions.visible, true, name + " workspace visibility");
  assert.equal(dimensions.innerWidth, width, name + " viewport width");
  assert.ok(dimensions.documentWidth <= width + 2,
    name + " must not scroll horizontally: " + JSON.stringify(dimensions));
  await browser.screenshot("workspace-" + name);
}
async function main() {
  const storage = mkdtempSync(join(tmpdir(), "gc-monitor-browser-"));
  const chromeProfile = mkdtempSync(join(tmpdir(), "gc-monitor-chrome-"));
  let service, chrome, browser;
  try {
    const port = await freePort();
    service = spawn("python3", ["-m", "monitor.server"], {
      env: {...process.env, GC_HOST: "127.0.0.1", GC_PORT: String(port),
        GC_DATA_DIR: storage, GC_ADMIN_PASSWORD: FIXTURE_PASSWORD,
        GC_COOKIE_SECURE: "0", GC_ALLOW_PRIVATE_TARGETS: "0",
        GC_NOTIFY_URL: "", GC_NOTIFY_TOKEN_FILE: ""},
      stdio: ["ignore", "ignore", "pipe"],
    });
    let serviceError = "";
    service.stderr.on("data", chunk => { serviceError = (serviceError + chunk).slice(-2000); });
    await waitFor(async () => {
      if (service.exitCode !== null) throw new Error("Monitor exited: " + serviceError);
      const response = await fetch("http://127.0.0.1:" + port + "/readyz");
      return response.ok && (await response.json()).ready === true;
    }, "local Monitor readiness");

    chrome = spawn(chromeBinary(), [
      "--headless=new", "--no-sandbox", "--disable-dev-shm-usage",
      "--no-first-run", "--no-default-browser-check", "--disable-gpu",
      "--disable-background-networking", "--disable-sync",
      "--disable-component-update", "--disable-extensions",
      "--remote-debugging-port=0", "--remote-allow-origins=*",
      "--user-data-dir=" + chromeProfile,
      "about:blank",
    ], { stdio: "ignore" });
    const debugPort = await waitFor(() => {
      if (chrome.exitCode !== null) throw new Error("Headless Chrome exited");
      const file = join(chromeProfile, "DevToolsActivePort");
      if (!existsSync(file)) return false;
      const value = Number(readFileSync(file, "utf8").split("\n")[0]);
      return value > 0 ? value : false;
    }, "Chrome debug port");

    const url = "http://127.0.0.1:" + port + "/";
    const tab = await createTab(debugPort, url);
    browser = new Browser(await openWebSocket(tab.webSocketDebuggerUrl));
    await browser.command("Page.enable");
    await browser.command("Runtime.enable");
    await browser.command("Page.navigate", {url});
    await waitFor(() => browser.evaluate(
      'document.querySelector("#login")?.hidden === false'), "login UI");

    // Avoid writing credentials, cookies, or token notices into artifacts.
    await browser.screenshot("login-desktop");
    assert.equal(await browser.evaluate('document.querySelector("#password").type'), "password");
    await browser.evaluate(`(() => {
      document.querySelector("#password").value = ${JSON.stringify(FIXTURE_PASSWORD)};
      document.querySelector("#login-form").requestSubmit();
    })()`);
    await waitFor(() => browser.evaluate(
      'document.querySelector("#workspace")?.hidden === false && document.querySelector("#stat-total")?.textContent !== "—"'),
      "authenticated workspace");
    assert.equal(await browser.evaluate(
      'document.querySelectorAll("[aria-current=page]").length'), 1);
    const addButton = await browser.evaluate(`({
      text: document.querySelector("#new-monitor").textContent,
      decorative: document.querySelector("#new-monitor span[aria-hidden=true]")?.textContent,
    })`);
    assert.equal(addButton.decorative, "+", "add-monitor icon uses portable glyph");
    assert.ok(addButton.text.includes("Add monitor"));
    await checkViewport(browser, "desktop", 1280, 800, false);

    // Create a private push monitor using the actual application form.
    await browser.evaluate(`(() => {
      document.querySelector("#new-monitor").click();
      document.querySelector("#monitor-name").value = ${JSON.stringify(TARGET_NAME)};
      const type = document.querySelector("#monitor-type");
      type.value = "push";
      type.dispatchEvent(new Event("change", {bubbles: true}));
      document.querySelector("#monitor-public").checked = false;
      document.querySelector("#monitor-form").requestSubmit();
    })()`);
    await waitFor(() => browser.evaluate(`document.querySelector("#monitor-list")?.textContent.includes(${JSON.stringify(TARGET_NAME)})`),
      "private push monitor creation");
    assert.equal(await browser.evaluate(
      'document.querySelector("#monitor-result-count").textContent'), "1 of 1 services");

    // Clear one-time push URL *before* any subsequent screenshot.
    await browser.evaluate(`(() => {
      const notice = document.querySelector("#notice");
      notice.textContent = "";
      notice.hidden = true;
      const search = document.querySelector("#monitor-search");
      search.value = "never-match";
      search.dispatchEvent(new Event("input", {bubbles: true}));
    })()`);
    assert.equal(await browser.evaluate(
      'document.querySelector("#monitor-result-count").textContent'), "0 of 1 services");
    await browser.evaluate(`(() => {
      const search = document.querySelector("#monitor-search");
      search.value = "private push";
      search.dispatchEvent(new Event("input", {bubbles: true}));
    })()`);
    assert.equal(await browser.evaluate(
      'document.querySelector("#monitor-result-count").textContent'), "1 of 1 services");
    await browser.evaluate(`(() => {
      const selector = document.querySelector("#monitor-status-filter");
      selector.value = "down";
      selector.dispatchEvent(new Event("change", {bubbles: true}));
    })()`);
    assert.equal(await browser.evaluate(
      'document.querySelector("#monitor-result-count").textContent'), "0 of 1 services");
    await browser.evaluate(`(() => {
      const selector = document.querySelector("#monitor-status-filter");
      selector.value = "all";
      selector.dispatchEvent(new Event("change", {bubbles: true}));
    })()`);

    // CDP sends a genuine keyboard Enter event to the focused nav button.
    await browser.evaluate(
      'document.querySelector("button[data-view=monitors]").focus()');
    assert.equal(await browser.evaluate('document.activeElement?.dataset.view'),
      "monitors", "navigation button takes keyboard focus");
    await browser.command("Input.dispatchKeyEvent", {
      type: "keyDown", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13,
      nativeVirtualKeyCode: 13,
      text: String.fromCharCode(13), unmodifiedText: String.fromCharCode(13),
    });
    await browser.command("Input.dispatchKeyEvent", {
      type: "keyUp", key: "Enter", code: "Enter", windowsVirtualKeyCode: 13,
      nativeVirtualKeyCode: 13,
    });
    await waitFor(() => browser.evaluate(
      'document.querySelector("button[data-view=monitors]").getAttribute("aria-current") === "page"'),
      "keyboard navigation and aria-current");

    await checkViewport(browser, "mobile", 390, 844, true);
    const navLayout = await browser.evaluate(`(() => {
      const nav = document.querySelector("#nav");
      const rect = nav.getBoundingClientRect();
      return {
        fits: nav.scrollWidth <= nav.clientWidth + 2,
        visible: [...nav.querySelectorAll("button[data-view]")].every(button => {
          const box = button.getBoundingClientRect();
          return box.width > 0 && box.height > 0 &&
            box.left >= rect.left - 2 && box.right <= rect.right + 2;
        }),
        rows: new Set([...nav.querySelectorAll("button[data-view]")].map(
          button => Math.round(button.getBoundingClientRect().top))).size,
      };
    })()`);
    assert.ok(navLayout.fits && navLayout.visible && navLayout.rows === 2,
      "mobile navigation must expose all items in two rows without scrolling: " +
      JSON.stringify(navLayout));
    const mobileCheck = await browser.evaluate(`({
      searchVisible: document.querySelector("#monitor-search").getBoundingClientRect().width > 0,
      statusVisible: document.querySelector("#monitor-status-filter").getBoundingClientRect().width > 0,
      privateNameVisible: document.querySelector("#monitor-list").textContent.includes(${JSON.stringify(TARGET_NAME)}),
    })`);
    assert.ok(mobileCheck.searchVisible && mobileCheck.statusVisible &&
      mobileCheck.privateNameVisible, "mobile service discovery visible");

    await browser.command("Page.navigate", {url: "http://127.0.0.1:" + port + "/status"});
    await waitFor(() => browser.evaluate(
      'document.querySelector("#public-page")?.hidden === false && document.querySelector("#public-list")?.textContent.length > 0'),
      "public status page");
    const publicView = await browser.evaluate(
      'document.querySelector("#public-list").textContent');
    assert.ok(!publicView.includes(TARGET_NAME), "private service hidden from public page");
    assert.ok(publicView.includes("Nothing published yet"), "empty public page state");
    await browser.screenshot("public-mobile");
    console.log("PASS: Chrome desktop and mobile login, private monitor, search, " +
      "status filtering, keyboard nav, accessible current item, privacy and no overflow");
    console.log("PASS: scrubbed screenshots: login-desktop, workspace-desktop, " +
      "workspace-mobile, public-mobile");
  } finally {
    if (browser) browser.close();
    if (chrome) chrome.kill("SIGTERM");
    if (service) service.kill("SIGTERM");
    await delay(250);
    rmSync(chromeProfile, {recursive: true, force: true});
    rmSync(storage, {recursive: true, force: true});
  }
}

main().catch(error => { console.error("FAIL: local-only browser acceptance:", error.message); process.exitCode = 1; });
