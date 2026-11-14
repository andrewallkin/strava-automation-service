#!/usr/bin/env node
/**
 * Capture README screenshots against docker-compose.standalone.yml (after migrate + seed).
 * Requires: npm install --prefix scripts playwright && npx --prefix scripts playwright install chromium
 */

import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");
const imagesDir = path.join(repoRoot, "docs", "images");

const baseUrl = (process.env.FRONTEND_URL ?? "http://127.0.0.1:3000").replace(/\/$/, "");
const viewport = { width: 1440, height: 900 };

const shots = [
  { file: "hero.png", path: "/" },
  { file: "feature-01.png", path: "/activities" },
  { file: "feature-02.png", path: "/events" },
];

async function main() {
  await mkdir(imagesDir, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport,
    deviceScaleFactor: 1,
  });

  const login = await context.request.post(`${baseUrl}/api/auth/login`);
  if (!login.ok()) {
    const body = await login.text();
    throw new Error(`Fast login failed (${login.status()}): ${body}`);
  }

  const page = await context.newPage();

  for (const shot of shots) {
    await page.goto(`${baseUrl}${shot.path}`, { waitUntil: "networkidle" });
    if (shot.file === "hero.png") {
      await page.getByRole("heading", { name: "Shoe Vault" }).waitFor({ timeout: 15_000 });
    }
    await page.waitForTimeout(400);
    await page.screenshot({
      path: path.join(imagesDir, shot.file),
      fullPage: false,
    });
    console.log(`Wrote ${shot.file}`);
  }

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});