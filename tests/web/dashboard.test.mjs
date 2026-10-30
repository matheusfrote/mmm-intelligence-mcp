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
import { instrumentBrowser, collectBrowser } from "./coverage.mjs";
import { browserUnits } from "./browser_units.mjs";
import { viewUnits } from "./view_units.mjs";
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
        args: ["--allow-file-access-from-files"],
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
      await instrumentBrowser(page);
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
        // hash changes before the hashchange handler replaces the previous view.
        await page.waitForFunction(
          (id) =>
            location.hash === "#" + id &&
            document.querySelector('nav a[aria-current="page"]')?.hash ===
              "#" + id &&
            document.querySelector("main").getAttribute("aria-busy") !== "true",
          id,
        );
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
      await nav("growth-datasets");
      assert.match(await page.locator("main").innerText(), /Acervo vazio/);
      await clickTool("Atualizar acervo", "storage_inventory");
      await nav("experiments");
      assert.equal(await page.getByLabel("ID do diagnóstico").inputValue(), "");
      await nav("data");
      const generated = await clickTool(
        "Gerar dados sintéticos",
        "generate_demo_dataset",
      );
      assert.equal(generated.rows, 156);
      await nav("overview");
      await page
        .getByRole("button", { name: "Ver qualidade", exact: true })
        .click();
      await idle();
      await nav("quality");
      const quality = await clickTool("Verificar qualidade", "data_quality");
      assert.equal(quality.valid, true);
      await nav("data");
      await page.getByText("Importar um arquivo CSV", { exact: true }).click();
      await page
        .locator("main form")
        .evaluate((form) =>
          form.dispatchEvent(new Event("submit", { cancelable: true })),
        );
      await idle();
      assert.match(await page.locator("#error").innerText(), /CSV UTF-8/);
      await page
        .locator('input[type="file"]')
        .setInputFiles(join(root, "docs/validation/v4/demo.csv"));
      const imported = await clickTool("Importar CSV", "import_csv");
      assert.equal(imported.validation.valid, true);
      await nav("modeling");
      await page.getByLabel("Motor estatístico").selectOption("pymc_marketing");
      assert.equal(
        JSON.parse(await page.getByLabel("Configuração do ajuste").inputValue())
          .draws,
        100,
      );
      await page.getByLabel("Motor estatístico").selectOption("ridge");
      const runtimes = await clickTool("Consultar runtimes", "backend_status");
      assert.ok(runtimes);
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
      await page.locator("#theme").selectOption("system");
      await page.emulateMedia({ colorScheme: "dark" });
      await page.waitForFunction(
        () => document.documentElement.dataset.theme === "dark",
      );
      assert.equal(
        await page.locator("html").getAttribute("data-theme"),
        "dark",
      );
      await page.emulateMedia({ colorScheme: "light" });
      await page.waitForFunction(
        () => document.documentElement.dataset.theme === "light",
      );
      assert.equal(
        await page.locator("html").getAttribute("data-theme"),
        "light",
      );
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
      for (const slider of await page
        .locator('main form input[type="range"]')
        .all()) {
        await slider.fill("0");
        await slider.dispatchEvent("input");
      }
      assert.ok(
        (await page.locator("main").innerText()).includes("Sem alocação"),
      );
      for (const slider of await page
        .locator('main form input[type="range"]')
        .all()) {
        await slider.fill("100");
        await slider.dispatchEvent("input");
      }
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
      await clickTool("Simular cenário", "simulate_budget");
      assert.equal(await page.locator("main table tbody tr").count(), 2);
      let exported = page.waitForEvent("download");
      await page
        .getByRole("button", { name: "Exportar cenário", exact: true })
        .click();
      assert.equal((await exported).suggestedFilename(), "cenario.json");
      await clickTool("Projetar plano", "forecast_model");
      exported = page.waitForEvent("download");
      await page
        .getByRole("button", { name: "Exportar projeção", exact: true })
        .click();
      assert.equal((await exported).suggestedFilename(), "projecao.json");
      await nav("results");
      await clickTool("Calcular auditoria e componentes", "audit_model");
      assert.match(await page.locator("main").innerText(), /reconciliação/);
      await nav("modeling");
      await clickTool("Treinar modelo", "train_mmm");
      await nav("comparison");
      await page
        .getByRole("button", { name: "Comparar modelos", exact: true })
        .click();
      await idle();
      assert.match(await page.locator("#error").innerText(), /dois a cinco/);
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
      for (const [label, tool, name] of [
        ["Exportar JSON", "export_analysis", "analise.json"],
        ["Exportar CSV", "export_analysis", "analise.csv"],
        ["Exportar MARKDOWN", "export_analysis", "analise.md"],
        ["Gerar relatório Markdown", "generate_report", "relatorio.md"],
      ]) {
        const pending = page.waitForEvent("download");
        await clickTool(label, tool);
        assert.equal((await pending).suggestedFilename(), name);
      }
      await page.locator("#refresh").click();
      await idle();
      const selectedDataset = await page.locator("#dataset").inputValue();
      await page.locator("#dataset").selectOption(selectedDataset);
      await page.locator("#dataset").dispatchEvent("change");
      await idle();
      const modelOption = await page
        .locator("#model option")
        .nth(1)
        .getAttribute("value");
      await page.locator("#model").selectOption(modelOption);
      await idle();
      const viewports = [];
      await nav("ingest-files");
      await page
        .getByRole("button", { name: "Pré-visualizar arquivo", exact: true })
        .click();
      await idle();
      assert.match(
        await page.locator("#error").innerText(),
        /Selecione um arquivo/,
      );
      await page
        .getByRole("button", {
          name: "Confirmar importação do original",
          exact: true,
        })
        .dispatchEvent("click");
      await idle();
      assert.match(
        await page.locator("#error").innerText(),
        /Pré-visualize novamente/,
      );
      await page
        .getByLabel("Arquivo fornecido")
        .setInputFiles({
          name: "too-large.csv",
          mimeType: "text/csv",
          buffer: Buffer.alloc(2 * 1024 * 1024 + 1, 120),
        });
      await page
        .getByRole("button", { name: "Pré-visualizar arquivo", exact: true })
        .click();
      await idle();
      assert.match(await page.locator("#error").innerText(), /2 MiB/);
      await page
        .getByLabel("Arquivo fornecido")
        .setInputFiles({
          name: "synthetic.xml",
          mimeType: "application/xml",
          buffer: Buffer.from(
            "<root><record><date>2026-01-05</date></record></root>",
          ),
        });
      await page.getByLabel("Formato declarado").selectOption("xml");
      await page
        .getByLabel("Campos e caminhos XML")
        .fill(JSON.stringify({ date: "date" }));
      await page
        .getByLabel("Referência de autorização para dados reais")
        .fill("synthetic-test-reference");
      await page
        .getByLabel("Este arquivo contém somente dados sintéticos")
        .check();
      const previewXML = await clickTool(
        "Pré-visualizar arquivo",
        "preview_dataset",
      );
      assert.equal(previewXML.preview[0].date, "2026-01-05");
      await page.evaluate(() => {
        window.realFileReaderForTest = FileReader;
        window.FileReader = class {
          readAsDataURL() {
            queueMicrotask(() => this.onerror());
          }
        };
      });
      await page
        .getByRole("button", { name: "Pré-visualizar arquivo", exact: true })
        .click();
      await idle();
      assert.match(
        await page.locator("#error").innerText(),
        /Não foi possível ler/,
      );
      await page.evaluate(() => {
        window.FileReader = window.realFileReaderForTest;
        delete window.realFileReaderForTest;
      });
      await page.getByLabel("Formato declarado").selectOption("csv");
      await page.getByLabel("Delimitador opcional").fill(",");
      await page
        .getByLabel("Aba da planilha (quando necessária)")
        .fill("synthetic-unused-for-csv");
      await clickTool("Carregar perfis disponíveis", "list_media_profiles");
      await page.getByLabel("Delimitador opcional").fill(",");
      await page
        .getByLabel("Aba da planilha (quando necessária)")
        .fill("declared-csv-no-worksheet");
      await page.getByLabel("Arquivo fornecido").setInputFiles({
        name: "synthetic.csv",
        mimeType: "text/csv",
        buffer: Buffer.from(
          "date,spend,clicks\n2026-01-05,10,2\n2026-01-12,20,3\n",
        ),
      });
      await page
        .getByLabel("Este arquivo contém somente dados sintéticos")
        .check();
      await clickTool("Pré-visualizar arquivo", "preview_dataset");
      const importedSource = await clickTool(
        "Confirmar importação do original",
        "import_source",
      );
      assert.equal(importedSource.artifact_type, "source");
      await page
        .getByLabel("Mapeamento de colunas")
        .fill(
          JSON.stringify({ date: "date", spend: "spend", clicks: "clicks" }),
        );
      await page
        .getByLabel("Unidades declaradas")
        .fill(JSON.stringify({ spend: "BRL", clicks: "count" }));
      await page.getByLabel("Dimensões e metodologia").fill(
        JSON.stringify({
          channel: "search",
          strategy: "paid",
          kpi_definition: "synthetic clicks",
        }),
      );
      const normalized = await clickTool(
        "Normalizar arquivo",
        "map_dataset_schema",
      );
      assert.equal(normalized.rows.length, 2);
      await nav("media-quality");
      const mediaReport = await clickTool(
        "Validar mídia selecionada",
        "validate_media_dataset",
      );
      assert.equal(mediaReport.dataset_applicability.state, "applicable");
      const crossmedia = await clickTool(
        "Validar cobertura crossmedia",
        "validate_crossmedia_dataset",
      );
      assert.equal(crossmedia.coverage_matrix.length, 1);
      await nav("growth-datasets");
      assert.ok(
        (await page.locator("main").innerText()).includes(
          normalized.artifact_id,
        ),
      );
      await clickTool("Atualizar acervo", "storage_inventory");
      // Exercise the dedicated routes against persisted artifacts and the same MCP services.
      const section = (title) =>
        page.locator("section.panel").filter({
          has: page.getByRole("heading", { name: title, exact: true }),
        });
      await nav("media-quality");
      const custom = section("Perfil personalizado");
      await custom.getByLabel("Nome do perfil").fill("browser_model");
      await custom
        .getByLabel("Campos obrigatórios")
        .fill(JSON.stringify(["date", "spend", "sales", "control"]));
      const customProfile = await clickTool(
        "Registrar perfil imutável",
        "register_media_profile",
      );
      await nav("ingest-files");
      const csv = ["date,spend,sales,control"];
      for (let i = 0; i < 104; i++) {
        const day = new Date(Date.UTC(2026, 0, 5 + i * 7))
          .toISOString()
          .slice(0, 10);
        csv.push(
          `${day},${50 + ((i * 7) % 13)},${100 + ((i * 11) % 17) + (i % 5)},${i % 5}`,
        );
      }
      await page.getByLabel("Arquivo fornecido").setInputFiles({
        name: "model.csv",
        mimeType: "text/csv",
        buffer: Buffer.from(csv.join("\n")),
      });
      await page
        .getByLabel("Este arquivo contém somente dados sintéticos")
        .check();
      await clickTool("Pré-visualizar arquivo", "preview_dataset");
      await clickTool("Confirmar importação do original", "import_source");
      await page
        .getByLabel("Perfil de mídia", { exact: true })
        .selectOption(customProfile.artifact_id);
      await page
        .getByLabel("Mapeamento de colunas")
        .fill(
          JSON.stringify(
            Object.fromEntries(
              ["date", "spend", "sales", "control"].map((k) => [k, k]),
            ),
          ),
        );
      await page
        .getByLabel("Unidades declaradas")
        .fill(JSON.stringify({ spend: "BRL", sales: "BRL", control: "index" }));
      await page.getByLabel("Dimensões e metodologia").fill(
        JSON.stringify({
          channel: "synthetic",
          strategy: "paid",
          kpi_definition: "fabricated revenue",
        }),
      );
      const modelFrame = await clickTool(
        "Normalizar arquivo",
        "map_dataset_schema",
      );
      assert.equal(modelFrame.rows.length, 104);
      await nav("combine");
      await page
        .getByRole("button", {
          name: "Materializar join revisado",
          exact: true,
        })
        .dispatchEvent("click");
      await idle();
      assert.match(await page.locator("#error").innerText(), /Revise a prévia/);
      await page
        .getByLabel("ID da fonte esquerda")
        .fill(normalized.artifact_id);
      await page.getByLabel("ID da fonte direita").fill(modelFrame.artifact_id);
      await page.getByLabel("Resolução de contexto").fill(
        JSON.stringify({
          kpi_definition:
            "synthetic sales and clicks retained in separate columns",
        }),
      );
      await page.getByLabel("Cardinalidade declarada").selectOption("1:m");
      const blockedJoin = await clickTool(
        "Pré-visualizar join",
        "join_datasets",
      );
      assert.equal(blockedJoin.blocked, true);
      assert.equal(
        await page
          .getByRole("button", {
            name: "Materializar join revisado",
            exact: true,
          })
          .isDisabled(),
        true,
      );
      await page.getByLabel("Cardinalidade declarada").selectOption("1:1");
      const joinPreview = await clickTool(
        "Pré-visualizar join",
        "join_datasets",
      );
      assert.equal(joinPreview.blocked, false);
      assert.equal(joinPreview.output_rows, 2);
      const joined = await clickTool(
        "Materializar join revisado",
        "join_datasets",
      );
      assert.equal(joined.rows.length, 2);
      assert.equal(joined.source_ids.length, 2);
      await nav("growth-analysis");
      const temporal = section("Evolução temporal");
      await temporal
        .getByLabel("ID do artefato selecionado")
        .fill(modelFrame.artifact_id);
      await temporal.getByLabel("Métricas para análise").fill('["sales"]');
      const trend = await clickTool("Analisar evolução", "analyze_growth");
      assert.equal(trend.groups[0].observations, 104);
      assert.ok((await page.locator("svg.chart").count()) > 0);
      const diagnosticPanel = section("Diagnóstico rastreável");
      await diagnosticPanel
        .getByLabel("ID do artefato selecionado")
        .fill(modelFrame.artifact_id);
      const diagnostic = await clickTool(
        "Criar diagnóstico",
        "create_growth_diagnostic",
      );
      assert.ok(diagnostic.artifact_id);
      await nav("mmm-prepare");
      for (const title of [
        "Elegibilidade do desenho",
        "Materialização para treino",
      ]) {
        const form = section(title);
        await form
          .getByLabel("ID do artefato selecionado")
          .fill(modelFrame.artifact_id);
        await form.getByLabel("KPI", { exact: true }).fill("sales");
        await form.getByLabel("Colunas de gastos").fill('["spend"]');
        await form.getByLabel("Colunas de controle").fill('["control"]');
      }
      const eligible = await clickTool(
        "Verificar elegibilidade MMM",
        "check_mmm_eligibility",
      );
      assert.equal(eligible.eligible, true);
      const prepared = await clickTool(
        "Preparar dataset de treino",
        "prepare_mmm_dataset",
      );
      assert.equal(prepared.training_tool, "train_mmm");
      const preparedFit = await clickTool(
        "Treinar dataset preparado",
        "train_mmm",
      );
      assert.ok(Number.isFinite(preparedFit.metrics.test.mae));
      await nav("experiments");
      const decisionForm = section("Proposta de decisão");
      for (const [label, value] of Object.entries({
        Problema: "Mudança descritiva",
        "Hipótese falsificável": "Verificar medição",
        "Ação proposta": "Inspeção manual",
        "KPI da decisão": "sales",
        "Período de baseline": "Primeiras semanas",
        "Horizonte esperado": "4 semanas",
        "Métricas de proteção": '["spend"]',
        "Riscos conhecidos": '["confounding"]',
      }))
        await decisionForm.getByLabel(label, { exact: true }).fill(value);
      const decision = await clickTool(
        "Registrar proposta",
        "create_growth_decision",
      );
      const transition = section("Revisão e histórico");
      await transition
        .getByLabel("ID do artefato selecionado")
        .fill(decision.artifact_id);
      await transition
        .getByLabel("Responsável declarado")
        .fill("Synthetic reviewer");
      await transition
        .getByLabel("Parecer e limitações")
        .fill("Observação sintética, sem recomendação real");
      const approved = await clickTool(
        "Registrar transição",
        "transition_growth_decision",
      );
      assert.equal(approved.state, "approved");
      await nav("ingest-files");
      const units = Array.from({ length: 200 }, (_, i) => ({
        unit: String(i),
        arm: i < 100 ? "control" : "treatment",
        outcome: Number(i % 10 < (i < 100 ? 2 : 4)),
        refunds: 0,
        cost: 2,
        date: "2026-01-15",
        eligible: "yes",
        event: "entry",
      }));
      await page.getByLabel("Arquivo fornecido").setInputFiles({
        name: "experiment.json",
        mimeType: "application/json",
        buffer: Buffer.from(JSON.stringify(units)),
      });
      await page
        .getByLabel("Formato declarado", { exact: true })
        .selectOption("json");
      await page
        .getByLabel("Este arquivo contém somente dados sintéticos")
        .check();
      await clickTool("Pré-visualizar arquivo", "preview_dataset");
      const experimentSource = await clickTool(
        "Confirmar importação do original",
        "import_source",
      );
      await nav("growth-analysis");
      const cohort = section("Retenção e conversão por coorte");
      await cohort
        .getByLabel("ID do artefato selecionado")
        .fill(experimentSource.artifact_id);
      await cohort.getByLabel("Períodos de acompanhamento").fill("3");
      const cohortResult = await clickTool(
        "Analisar coortes",
        "analyze_cohorts",
      );
      assert.equal(cohortResult.cohorts[0].entry_population, 200);
      assert.equal(cohortResult.cohorts[0].periods[0].rate, 0);
      assert.equal(cohortResult.cohorts[0].periods[2].rate, null);
      await nav("experiments");
      const stats = section("Planejamento estatístico");
      for (const [label, value] of Object.entries({
        "População elegível": "fabricated eligible accounts",
        "Janela de mensuração": "2026-01-01/2026-01-31",
        "Regra de parada": "fixed horizon",
        "Guardrails planejados": '["refunds"]',
        "Hipótese do plano estatístico": "T changes conversion by .1",
        "Plano de análise declarado":
          "independent unit ITT, complete cases with attrition warning",
        "Coluna da unidade de randomização": "unit",
        "Duração em dias (número ou null)": "31",
        "Janela de conversão em dias (número ou null)": "7",
        "Início verificável (AAAA-MM-DD)": "2026-01-01",
        "Fim verificável (AAAA-MM-DD)": "2026-01-31",
        "Coluna da data observada": "date",
        "Coluna de elegibilidade": "eligible",
        "Valor elegível dessa coluna": "yes",
        "Critérios de exclusão declarados": "No exclusions",
        "Restrições operacionais": "No live actions",
        "Tamanho da família de comparações": "2",
        "Coluna de custo por unidade (opcional)": "cost",
        "Desfechos, direção adversa e limiar das proteções": JSON.stringify({
          refunds: {
            outcome_type: "binary",
            direction: "increase",
            max_adverse_change: 0.1,
          },
        }),
      }))
        await stats.getByLabel(label, { exact: true }).fill(value);
      const statisticalPlan = await clickTool(
        "Planejar experimento",
        "plan_experiment",
      );
      assert.equal(statisticalPlan.protocol_complete, true);
      const analysisForm = section("Análise dos resultados importados");
      await analysisForm
        .getByLabel("ID do artefato selecionado")
        .fill(experimentSource.artifact_id);
      await analysisForm
        .getByLabel("ID do plano estatístico")
        .fill(statisticalPlan.artifact_id);
      const statisticalResult = await clickTool(
        "Analisar experimento",
        "analyze_experiment",
      );
      assert.ok(Math.abs(statisticalResult.estimate.difference - 0.2) < 1e-10);
      assert.equal(statisticalResult.cost_per_conversion.treatment, 5);
      assert.equal(statisticalResult.causal_identification, false);
      assert.equal(statisticalResult.population_verified, true);
      await nav("growth-reports");
      const reportPanel = section("Recuperar relatório ou artefato");
      await reportPanel
        .getByLabel("ID do artefato selecionado")
        .fill(trend.artifact_id);
      const report = await clickTool(
        "Recuperar resultado persistido",
        "get_growth_artifact",
      );
      assert.equal(report.artifact_id, trend.artifact_id);
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
      await browserUnits(page);
      await viewUnits(page);
      const native = await new Promise((resolve, reject) => {
        const seed = spawn(python, ["tests/web/seed_native.py", data], {
          cwd: root,
          windowsHide: true,
        });
        let result = "",
          error = "";
        seed.stdout.on("data", (b) => (result += b));
        seed.stderr.on("data", (b) => (error += b));
        seed.on("error", reject);
        seed.on("close", (code) =>
          code === 0 ? resolve(JSON.parse(result)) : reject(new Error(error)),
        );
      });
      await page.evaluate(() => {
        document.querySelector("#refresh").dispatchEvent(new Event("click"));
        window.dispatchEvent(new HashChangeEvent("hashchange"));
      });
      await idle();
      await page.locator("#dataset").selectOption(native.dataset_id);
      await idle();
      await page
        .locator("#model")
        .selectOption("backend_models:" + native.model_id);
      await idle();
      await nav("results");
      assert.equal(
        (await page.locator(".metric strong").allTextContents())[0],
        new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(
          native.mae,
        ),
      );
      const offline = await browser.newPage();
      await instrumentBrowser(offline);
      await offline.goto(
        pathToFileURL(join(root, "src/mmm_intelligence/web/index.html")).href,
      );
      await offline.waitForFunction(() =>
        document
          .querySelector("#error")
          .textContent.includes("Abra pelo servidor local"),
      );
      await offline.locator('nav a[href="#data"]').click();
      await offline.waitForFunction(() => location.hash === "#data");
      assert.match(
        await offline.locator("main").innerText(),
        /Carregando o workspace local/,
      );
      assert.equal(await offline.locator("main button").count(), 0);
      await collectBrowser([page, offline], "dashboard");
      await offline.close();
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
