// Test-only instrumentation: production assets and CSP remain unchanged.
import { createRequire } from "node:module";
import assert from "node:assert/strict";
import { mkdir, writeFile, readdir, readFile } from "node:fs/promises";
import { basename, resolve, join } from "node:path";
const require = createRequire(import.meta.url);
const { createInstrumenter } = require("istanbul-lib-instrument");
const { createCoverageMap } = require("istanbul-lib-coverage");
const { createContext } = require("istanbul-lib-report");
const reports = require("istanbul-reports");

export async function instrumentBrowser(page) {
  const instrumenter = createInstrumenter({
    esModules: true,
    compact: false,
    coverageGlobalScope: "window",
    coverageGlobalScopeFunc: false,
  });
  await page.route("**/app/*.js", async (route) => {
    if (new URL(route.request().url()).protocol === "file:") {
      const file = resolve(
        "src/mmm_intelligence/web",
        basename(new URL(route.request().url()).pathname),
      );
      return route.fulfill({
        contentType: "text/javascript",
        body: instrumenter.instrumentSync(await readFile(file, "utf8"), file),
      });
    }
    const response = await route.fetch();
    if (!response.ok()) return route.fulfill({ response });
    const file = resolve(
      "src/mmm_intelligence/web",
      basename(new URL(route.request().url()).pathname),
    );
    const source = await response.text();
    assert.equal(
      source,
      await readFile(file, "utf8"),
      "Server must serve the current checkout: " + file,
    );
    await route.fulfill({
      response,
      body: instrumenter.instrumentSync(source, file),
    });
  });
  await page.route("**/mmm_intelligence/web/*.js", async (route) => {
    const file = resolve(
      "src/mmm_intelligence/web",
      basename(new URL(route.request().url()).pathname),
    );
    await route.fulfill({
      contentType: "text/javascript",
      body: instrumenter.instrumentSync(await readFile(file, "utf8"), file),
    });
  });
}

export async function collectBrowser(pages, name) {
  const map = createCoverageMap({});
  for (const page of Array.isArray(pages) ? pages : [pages])
    map.merge(await page.evaluate(() => window.__coverage__ ?? {}));
  const raw = map.toJSON();
  const dir = resolve("evidence/javascript-coverage");
  await mkdir(dir, { recursive: true });
  await writeFile(join(dir, `${name}-raw.json`), JSON.stringify(raw));
  // Every first-party JS asset enters the denominator, even if never imported.
  const instrumenter = createInstrumenter({ esModules: true });
  const sourceRoot = resolve("src/mmm_intelligence/web");
  for (const entry of await readdir(sourceRoot)) {
    if (!entry.endsWith(".js")) continue;
    const filename = join(sourceRoot, entry);
    if (map.files().includes(filename)) continue;
    instrumenter.instrumentSync(await readFile(filename, "utf8"), filename);
    map.addFileCoverage(instrumenter.lastFileCoverage());
  }
  const context = createContext({ dir: join(dir, name), coverageMap: map });
  reports.create("json-summary").execute(context);
  reports.create("html").execute(context);
  reports.create("text-summary").execute(context);
  return map.getCoverageSummary().toJSON();
}
