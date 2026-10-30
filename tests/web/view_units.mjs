import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

/** Render contracts use actual synthetic results from the real four-engine demo. */
export async function viewUnits(page) {
  const fixture = JSON.parse(
    await readFile(resolve("tests/fixtures/dashboard-models.json"), "utf8"),
  );
  assert.equal(fixture.synthetic, true);
  const result = await page.evaluate(async (fixture) => {
    const { views } = await import("/app/views.js");
    const root = document.createElement("div");
    const noIO = () => {
      throw new Error("Pure view rendering must not perform I/O");
    };
    const context = (state) => ({
      root,
      state,
      run: noIO,
      call: noIO,
      refresh: noIO,
      loadModel: noIO,
      render: noIO,
    });
    const titles = [];
    for (const [backend, item] of Object.entries(fixture.models)) {
      const state = {
        backend,
        dataset: item.dataset,
        datasetId: item.model.dataset_id,
        model: item.model,
        analysis: item.analysis,
        inventory: [
          {
            kind: backend === "ridge" ? "models" : "backend_models",
            model_id: item.model.model_id,
            artifact_id: item.model.model_id,
            dataset_id: item.model.dataset_id,
          },
        ],
        scenarios: [],
      };
      for (const name of [
        "overview",
        "data",
        "quality",
        "modeling",
        "results",
        "comparison",
        "response",
        "simulation",
        "insights",
        "reports",
      ]) {
        root.replaceChildren();
        views[name](context(state));
        if (root.querySelectorAll("h1").length !== 1)
          throw new Error("Missing view title: " + name);
        titles.push(backend + ":" + name);
        if (
          name === "response" &&
          backend !== "ridge" &&
          !root.textContent.includes("indisponíveis")
        )
          throw new Error("Native curve fallback must be explicit");
        if (name === "data") {
          const filter = root.querySelector('input[type="text"]');
          filter.value = "no-matching-row";
          filter.dispatchEvent(new Event("input"));
          if (!root.textContent.includes("0 registros"))
            throw new Error("Data filter did not update");
          filter.value = "";
          filter.dispatchEvent(new Event("input"));
          const buttons = [...root.querySelectorAll("button")];
          buttons.find((button) => button.textContent === "Próxima").click();
          if (!root.textContent.includes("Página 2"))
            throw new Error("Pagination did not advance");
          buttons.find((button) => button.textContent === "Anterior").click();
          if (!root.textContent.includes("Página 1"))
            throw new Error("Pagination did not rewind");
        }
      }
    }
    const emptyState = {
      dataset: null,
      model: null,
      analysis: null,
      datasetId: "",
      backend: "ridge",
      inventory: [],
      scenarios: [],
    };
    const empty = [];
    for (const name of [
      "overview",
      "data",
      "quality",
      "modeling",
      "results",
      "comparison",
      "response",
      "simulation",
      "insights",
      "reports",
    ]) {
      root.replaceChildren();
      views[name](context(emptyState));
      empty.push(
        root.textContent.includes("Comece pelos dados") ||
          root.textContent.includes("Selecione um modelo"),
      );
    }
    const first = fixture.models.ridge;
    const legacyState = {
      ...emptyState,
      inventory: [
        { model_id: "old", artifact_id: "unrelated", dataset_id: "another" },
      ],
      dataset: { ...first.dataset, synthetic: false, column_spec: undefined },
    };
    root.replaceChildren();
    views.overview(context(legacyState));
    if (!root.textContent.includes("Declarada"))
      throw new Error("Declared provenance disappeared");
    views.modeling(context(legacyState));
    const legacyRows = first.dataset.rows.map(({ date, ...row }) => ({
      report_day: date,
      ...row,
    }));
    root.replaceChildren();
    views.data(
      context({
        ...legacyState,
        dataset: { ...legacyState.dataset, rows: legacyRows },
      }),
    );
    if (
      ![...root.querySelectorAll("svg text")].some(
        (n) => n.textContent === legacyRows.at(-1).report_day,
      )
    )
      throw new Error("Legacy first-column date fallback failed");
    root.replaceChildren();
    views.overview(
      context({ ...legacyState, analysis: first.analysis, backend: "legacy" }),
    );
    if (!root.textContent.includes("legacy"))
      throw new Error("Unknown legacy engine label lost");
    root.replaceChildren();
    views.simulation(
      context({
        ...legacyState,
        model: first.model,
        analysis: {
          ...first.analysis,
          request: { ...first.analysis.request, control_columns: undefined },
        },
      }),
    );
    root.replaceChildren();
    const { growthViews } = await import("/app/growth_views.js");
    const incomplete = {
      groups: [{ segment: {}, metrics: { sales: { status: "insufficient" } } }],
      synthetic: true,
    };
    growthViews["growth-analysis"](
      context({
        ...emptyState,
        growth: {
          forms: {},
          artifacts: [],
          profiles: [],
          results: { analyze_growth: incomplete },
        },
      }),
    );
    if (root.querySelector("svg"))
      throw new Error("Insufficient metrics must not fabricate a chart");
    if (!root.textContent.includes("insufficient"))
      throw new Error("Missing metric status lost");
    [...root.querySelectorAll("button")]
      .find((n) => n.textContent === "Exportar este resultado")
      .click();
    const rows = first.dataset.rows.map(({ date, ...rest }) => ({
      ...rest,
      report_day: date,
    }));
    const alias = {
      ...first.dataset,
      rows,
      column_spec: { ...first.dataset.column_spec, date_column: "report_day" },
    };
    root.replaceChildren();
    views.data(
      context({ ...emptyState, dataset: alias, datasetId: "custom-date" }),
    );
    const chartLabels = [...root.querySelectorAll("svg text")].map(
      (node) => node.textContent,
    );
    return {
      titles,
      empty,
      chartLabels,
      firstDate: rows[0].report_day,
      lastDate: rows.at(-1).report_day,
    };
  }, fixture);
  assert.equal(result.titles.length, 40);
  assert.ok(result.empty.every(Boolean));
  assert.ok(
    result.chartLabels.includes(result.firstDate) &&
      result.chartLabels.includes(result.lastDate),
    "Chart must use the declared date column even when it is not the first field: " +
      JSON.stringify(result),
  );
  const callback = await page.evaluate(async (fixture) => {
    const { views } = await import("/app/views.js");
    const item = fixture.models.pymc_marketing;
    const root = document.createElement("div"),
      calls = [],
      pending = [];
    const state = {
      dataset: item.dataset,
      datasetId: item.model.dataset_id,
      model: item.model,
      analysis: item.analysis,
      backend: "pymc_marketing",
      scenarios: [],
      inventory: [
        {
          kind: "models",
          artifact_id: "ridge-contract",
          dataset_id: item.model.dataset_id,
        },
        {
          kind: "backend_models",
          artifact_id: item.model.model_id,
          dataset_id: item.model.dataset_id,
        },
      ],
    };
    const ctx = {
      root,
      state,
      run: (_, action) => pending.push(action()),
      refresh: async (preferred) => calls.push(["refresh", preferred]),
      call: async (name, args) => {
        calls.push([name, args]);
        if (name === "train_backend" || name === "get_backend_model")
          return item.model;
        if (name === "compare_models")
          return {
            models: [
              {
                backend: "ridge",
                model_id: "ridge-contract",
                metrics: fixture.models.ridge.analysis.metrics,
              },
              {
                backend: "pymc_marketing",
                model_id: item.model.model_id,
                metrics: item.analysis.metrics,
              },
            ],
          };
        if (name === "data_quality")
          return {
            valid: false,
            columns: {},
            alerts: [{ severity: "blocking", code: "contract-invalid" }],
          };
        throw new Error("Unexpected UI-boundary call: " + name);
      },
    };
    views.modeling(ctx);
    const engine = root.querySelector("select");
    engine.value = "pymc_marketing";
    engine.dispatchEvent(new Event("change"));
    root
      .querySelector("form")
      .dispatchEvent(new Event("submit", { cancelable: true }));
    await pending.pop();
    root.replaceChildren();
    views.comparison(ctx);
    root
      .querySelectorAll('input[type="checkbox"]')
      .forEach((n) => (n.checked = true));
    [...root.querySelectorAll("button")]
      .find((n) => n.textContent === "Comparar modelos")
      .click();
    await pending.pop();
    if (!root.textContent.includes("pymc_marketing"))
      throw new Error("Native comparison result absent");
    root.replaceChildren();
    views.quality(ctx);
    root.querySelector("button").click();
    await pending.pop();
    if (!root.textContent.includes("impedem a modelagem"))
      throw new Error("Invalid quality result appears valid");
    return calls;
  }, fixture);
  assert.equal(
    callback.find(([name]) => name === "train_backend")[1].backend,
    "pymc_marketing",
  );
  assert.equal(
    callback.find(([name]) => name === "compare_models")[1].models[1].backend,
    "pymc_marketing",
  );
}
