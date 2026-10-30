import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

/** Real DOM modules, with HTTP failure fixtures only at the fetch boundary. */
export async function browserUnits(page) {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const result = await page.evaluate(async () => {
    const { MCPClient } = await import("/app/client.js");
    const { lineChart } = await import("/app/charts.js");
    const ui = await import("/app/ui.js");
    const original = window.fetch;
    const observed = [];
    const messages = [];
    const client = new MCPClient();
    try {
      const cases = [
        [429, {}, "rpc"],
        [503, {}, "rpc"],
        [200, { error: { message: "protocol failure" } }, "rpc"],
        [200, { error: {} }, "rpc"],
        [
          200,
          {
            result: {
              isError: true,
              structuredContent: {
                ok: false,
                error: { code: "DENIED", message: "blocked" },
              },
            },
          },
          "call",
        ],
        [200, { result: { content: [{ text: "plain error" }] } }, "call"],
        [200, { result: {} }, "call"],
      ];
      for (const [status, body, method] of cases) {
        window.fetch = async (url, options) => {
          observed.push({
            url,
            body: JSON.parse(options.body),
            headers: options.headers,
          });
          return new Response(JSON.stringify(body), { status });
        };
        try {
          await client[method]("fixture");
          messages.push("DID_NOT_FAIL");
        } catch (error) {
          messages.push(error.message);
        }
      }
      window.fetch = async () =>
        new Response(
          JSON.stringify({
            result: { structuredContent: { ok: true, data: { value: 42 } } },
          }),
          { status: 200 },
        );
      const successful = await client.call("fixture");
      let encoded;
      window.fetch = async (url, options) => {
        encoded = JSON.parse(options.body).params.uri;
        return new Response(
          JSON.stringify({
            result: { contents: [{ text: '{"synthetic":true}' }] },
          }),
          { status: 200 },
        );
      };
      const dataset = await client.dataset("a /?");
      const container = ui.el("div");
      container.id = "unit-module-fixtures";
      container.style.width = "840px";
      const empty = lineChart([], []);
      empty
        .querySelector("svg")
        .dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight" }));
      const unnamed = lineChart([{ value: 1 }], ["value"]);
      if (
        [...unnamed.querySelectorAll("svg text")]
          .slice(-2)
          .some((n) => n.textContent !== "")
      )
        throw new Error("Undeclared chart dates must stay blank");
      const keys = [
        "unknown",
        "spend_search",
        "spend_social",
        "spend_video",
        "fifth",
        "sixth",
      ];
      const rows = Array.from({ length: 3 }, (_, i) => ({
        date: i === 0 ? '2026"quoted' : `2026-01-0${i + 1}`,
        ...Object.fromEntries(
          keys.map((k) => [k, k === "unknown" && i === 1 ? null : 5]),
        ),
      }));
      const chart = lineChart(rows, keys, { label: "Module fixture chart" });
      chart.id = "unit-interactive-chart";
      container.append(empty, chart);
      const noValues = empty.textContent.includes("Sem valores");
      const paths = chart.querySelectorAll("path");
      const segments = (paths[0].getAttribute("d").match(/M/g) || []).length;
      for (const checkbox of chart.querySelectorAll('input[type="checkbox"]')) {
        checkbox.checked = false;
        checkbox.dispatchEvent(new Event("change"));
      }
      const deselected = chart.textContent.includes("Sem valores");
      for (const checkbox of chart.querySelectorAll('input[type="checkbox"]')) {
        checkbox.checked = true;
        checkbox.dispatchEvent(new Event("change"));
      }
      const sliders = chart.querySelectorAll('input[type="range"]');
      sliders[0].value = "2";
      sliders[1].value = "0";
      sliders[0].dispatchEvent(new Event("input"));
      const reverseWindow = chart.querySelectorAll("path").length;
      sliders[0].value = "0";
      sliders[1].value = "2";
      sliders[0].dispatchEvent(new Event("input"));
      const fields = ui.table(
        [{ v: null, n: NaN, object: { count: 1 } }],
        [
          { key: "v", label: "Missing" },
          { key: "n", label: "Number" },
          { key: "object", label: "Object" },
          "absent",
        ],
      );
      const tableText = fields.textContent;
      const defaultSelect = ui.select("Empty selection", [], undefined).input
        .value;
      document.body.append(container);
      return {
        messages,
        successful,
        dataset,
        encoded,
        observed,
        noValues,
        deselected,
        segments,
        paths: paths.length,
        reverseWindow,
        tableText,
        defaultSelect,
      };
    } finally {
      window.fetch = original;
    }
  });
  assert.deepEqual(result.messages, [
    "Servidor HTTP 429 — aguarde antes de repetir",
    "Servidor HTTP 503",
    "protocol failure",
    "Falha no protocolo MCP",
    "DENIED: blocked",
    "plain error",
    "Resposta MCP inválida",
  ]);
  assert.equal(result.successful.value, 42);
  assert.equal(result.dataset.synthetic, true);
  assert.equal(result.encoded, "mmm://datasets/a%20%2F%3F");
  assert.ok(
    result.observed.every(
      (item) => item.url === "/app/mcp" && !item.headers.Authorization,
    ),
  );
  assert.equal(result.noValues, true);
  assert.equal(result.deselected, true);
  assert.equal(result.segments, 2);
  assert.equal(result.paths, 6);
  assert.equal(result.reverseWindow, 6);
  assert.ok(
    result.tableText.includes("Indisponível") &&
      result.tableText.includes('"count":1'),
  );
  assert.equal(result.defaultSelect, "");
  const chart = page.locator("#unit-interactive-chart svg");
  await chart.focus();
  await chart.press("ArrowRight");
  assert.ok(
    (
      await page.locator("#unit-interactive-chart .chart-tip").innerText()
    ).startsWith("2026-01-02"),
  );
  await chart.press("ArrowLeft");
  await chart.press("Enter");
  const bounds = await chart.boundingBox();
  await page.mouse.move(
    bounds.x + bounds.width - 1,
    bounds.y + bounds.height / 2,
  );
  assert.ok(
    (
      await page.locator("#unit-interactive-chart .chart-tip").innerText()
    ).startsWith("2026-01-03"),
  );
  const pending = page.waitForEvent("download");
  await page
    .locator("#unit-interactive-chart")
    .getByRole("button", { name: "Exportar série CSV" })
    .click();
  const exported = await pending;
  const filename = resolve("evidence/javascript-coverage/fixture-series.csv");
  await exported.saveAs(filename);
  const csv = await readFile(filename, "utf8");
  assert.ok(csv.includes('"2026""quoted"') && csv.includes('"unknown"'));
  await page.locator("#unit-module-fixtures").evaluate((node) => node.remove());
}
