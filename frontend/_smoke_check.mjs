import { chromium } from "playwright-core";

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });

await page.goto("http://localhost:3001/login", { waitUntil: "networkidle" });
await page.waitForSelector("text=Nexgile", { timeout: 15000 });
await page.screenshot({ path: "login.png" });

console.log("TITLE:", await page.title());
console.log("ERRORS:", JSON.stringify(errors));
await browser.close();
