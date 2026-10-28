import assert from "node:assert/strict";
import { test } from "node:test";
import { spawn } from "node:child_process";
import { mkdtemp, mkdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve, join } from "node:path";
import { createServer } from "node:net";
import { chromium } from "playwright";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
const require = createRequire(import.meta.url);

test(
  "local dashboard opens without credentials and completes the real synthetic workflow",
  { timeout: 180000 },
  async () => {
    const root = resolve("."),
      data = await mkdtemp(join(tmpdir(), "mmm-dashboard-"));
    const evidence = join(root, "evidence", "v42-browser");
    await mkdir(evidence, { recursive: true });
    const socket = createServer();
    await new Promise((r) => socket.listen(0, "127.0.0.1", r));
    const port = socket.address().port;
    await new Promise((r) => socket.close(r));
    const python =
      process.env.MMM_TEST_PYTHON ??
      join(root, "var", "envs", "security31", "Scripts", "python.exe");
    const child = spawn(
      python,
      ["-m", "mmm_intelligence.cli", "dashboard", "--port", String(port)],
      {
        cwd: root,
        env: {
          ...process.env,
          MMM_DATA_DIR: data,
          MMM_ALLOW_REAL_DATA: "false",
        },
        stdio: ["ignore", "pipe", "pipe"],
        windowsHide: true,
      },
    );
    let log = "";
    child.stdout.on("data", (b) => (log += b));
    child.stderr.on("data", (b) => (log += b));
    let browser;
    try {
      const url = `http://127.0.0.1:${port}/app`;
      let ready = false;
      for (let i = 0; i < 80; i++) {
        try {
          if ((await fetch(url)).ok) {
            ready = true;
            break;
          }
        } catch {}
        await new Promise((r) => setTimeout(r, 100));
      }
      assert.ok(ready, log);
      browser = await chromium.launch({
        ...(process.env.MMM_TEST_BROWSER === "chromium"
          ? {}
          : { channel: "chrome" }),
        headless: true,
      });
      const page = await browser.newPage({
          viewport: { width: 1440, height: 1000 },
        }),
        errors = [],
        requests = [];
      page.on("pageerror", (error) => errors.push(error.message));
      page.on("request", (r) => {
        if (r.url().includes("/app/mcp")) requests.push(r.headers());
      });
      await page.goto(
        pathToFileURL(join(root, "docs/validation/v4/dashboard.html")).href,
      );
      await page.screenshot({
        path: join(evidence, "before-offline.png"),
        fullPage: true,
      });
      await page.goto(url);
      await page.waitForFunction(() =>
        document.querySelector("#status").textContent.includes("Concluído"),
      );
      assert.equal(
        await page.locator("input[type=password],#login,#token").count(),
        0,
      );
      assert.equal(
        (
          await fetch(`http://127.0.0.1:${port}/mcp`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: "{}",
          })
        ).status,
        401,
      );
      const nav = async (id) => {
        await page.locator(`nav a[href="#${id}"]`).click();
        await page.waitForFunction((id) => location.hash === "#" + id, id);
      };
      const idle = () =>
        page.waitForFunction(
          () =>
            document.querySelector("main").getAttribute("aria-busy") !== "true",
        );
      async function clickTool(label, tool) {
        const response = page.waitForResponse(
          (r) =>
            r.url().endsWith("/app/mcp") &&
            r.request().postDataJSON()?.params?.name === tool,
        );
        await page.getByRole("button", { name: label, exact: true }).click();
        const payload = (await (await response).json()).result
          .structuredContent;
        assert.equal(payload.ok, true, JSON.stringify(payload.error));
        await idle();
        return payload.data;
      }
      await nav("data");
      const generated = await clickTool(
        "Gerar dados sintéticos",
        "generate_demo_dataset",
      );
      assert.equal(generated.rows, 156);
      await nav("quality");
      const quality = await clickTool("Verificar qualidade", "data_quality");
      assert.equal(quality.valid, true);
      await nav("data");
      await page.getByText("Importar um arquivo CSV", { exact: true }).click();
      await page
        .locator('input[type="file"]')
        .setInputFiles(join(root, "docs/validation/v4/demo.csv"));
      const imported = await clickTool("Importar CSV", "import_csv");
      assert.equal(imported.validation.valid, true);
      await nav("modeling");
      const trained = await clickTool("Treinar modelo", "train_mmm");
      await page.waitForFunction(
        () => document.querySelector("main h1").textContent === "Resultados",
      );
      const display = await page.locator(".metric strong").allTextContents();
      assert.equal(
        display[0],
        new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(
          trained.metrics.test.mae,
        ),
      );
      await nav("overview");
      await page.screenshot({
        path: join(evidence, "dashboard-light.png"),
        fullPage: true,
      });
      const tip = page.locator(".chart-tip");
      const before = await tip.textContent();
      await page.locator("svg.chart").focus();
      await page.keyboard.press("ArrowRight");
      assert.notEqual(await tip.textContent(), before);
      const paths = await page.locator("svg.chart path").count();
      await page.locator(".chart-controls input").first().uncheck();
      assert.equal(await page.locator("svg.chart path").count(), paths - 1);
      await page.locator("#theme").selectOption("dark");
      await page.screenshot({
        path: join(evidence, "dashboard-dark.png"),
        fullPage: true,
      });
      // Test-only interception lets axe run under the real same-origin CSP.
      await page.route("**/app/axe-test.js", (route) =>
        route.fulfill({
          path: require.resolve("axe-core/axe.min.js"),
          contentType: "text/javascript",
        }),
      );
      await page.addScriptTag({ url: "/app/axe-test.js" });
      const accessibility = [];
      for (const theme of ["light", "dark"]) {
        await page.locator("#theme").selectOption(theme);
        const scan = await page.evaluate(
          async () =>
            await axe.run(document, {
              runOnly: {
                type: "tag",
                values: ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"],
              },
            }),
        );
        accessibility.push({
          theme,
          violations: scan.violations.map((v) => ({
            id: v.id,
            impact: v.impact,
            nodes: v.nodes.map((n) => ({
              target: n.target,
              summary: n.failureSummary,
            })),
          })),
        });
      }
      await nav("simulation");
      const scenario = await clickTool("Simular cenário", "simulate_budget");
      assert.equal(
        (await page.locator(".metric strong").allTextContents())[0],
        new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(
          scenario.predicted_total,
        ),
      );
      const optimized = await clickTool(
        "Calcular candidato com restrições",
        "optimize_budget",
      );
      assert.equal(optimized.recommended_spend, null);
      await nav("modeling");
      await clickTool("Treinar modelo", "train_mmm");
      await nav("comparison");
      for (const checkbox of await page
        .locator('main input[type="checkbox"]')
        .all())
        await checkbox.check();
      const comparison = await clickTool("Comparar modelos", "compare_models");
      assert.equal(comparison.winner, null);
      assert.equal(comparison.models.length, 2);
      await nav("response");
      assert.equal(await page.locator("svg.chart").count(), 6);
      await nav("insights");
      assert.ok(
        (await page.locator("main").innerText()).includes("associações"),
      );
      await nav("reports");
      const downloadable = page.waitForEvent("download");
      await clickTool("Exportar dashboard HTML offline", "render_dashboard");
      assert.equal((await downloadable).suggestedFilename(), "dashboard.html");
      const viewports = [];
      for (const width of [320, 390, 768, 1024, 1440]) {
        await page.setViewportSize({ width, height: 900 });
        await nav("overview");
        viewports.push(
          await page.evaluate(() => ({
            width: innerWidth,
            scrollWidth: document.documentElement.scrollWidth,
          })),
        );
      }
      await page.setViewportSize({ width: 390, height: 844 });
      await page.screenshot({
        path: join(evidence, "dashboard-mobile.png"),
        fullPage: true,
      });
      assert.ok(requests.length > 10);
      assert.ok(requests.every((h) => !("authorization" in h)));
      assert.equal(
        await page.evaluate(() => localStorage.length + sessionStorage.length),
        0,
      );
      await writeFile(
        join(evidence, "results.json"),
        JSON.stringify(
          {
            login: false,
            mcpWithoutToken: 401,
            requests: requests.length,
            metrics: trained.metrics.test,
            scenarioTotal: scenario.predicted_total,
            viewports,
            accessibility,
            errors,
          },
          null,
          2,
        ),
      );
      assert.deepEqual(errors, []);
      assert.ok(
        viewports.every((v) => v.width === v.scrollWidth),
        JSON.stringify(viewports),
      );
      assert.ok(
        accessibility.every((a) => a.violations.length === 0),
        JSON.stringify(accessibility),
      );
    } finally {
      await browser?.close();
      child.kill();
      await writeFile(join(evidence, "server.log"), log);
    }
  },
);
