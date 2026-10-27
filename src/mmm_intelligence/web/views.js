import {
  el,
  panel,
  detail,
  button,
  field,
  select,
  jsonInput,
  download,
  table,
  metrics,
  empty,
  fmt,
  engines,
} from "./ui.js";
import { lineChart } from "./charts.js";
export const modules = [
  ["overview", "Visão geral"],
  ["data", "Data Explorer"],
  ["quality", "Qualidade"],
  ["modeling", "Modelagem"],
  ["results", "Resultados"],
  ["comparison", "Comparação"],
  ["response", "Resposta de mídia"],
  ["simulation", "Simulador"],
  ["insights", "Insights"],
  ["reports", "Relatórios"],
];
function head(ctx, id, subtitle) {
  const h = el("div", "", "page-head"),
    left = el("div");
  left.append(
    el("span", "MMM / INTELLIGENCE", "eyebrow"),
    el("h1", modules.find((m) => m[0] === id)[1]),
    el("p", subtitle),
  );
  h.append(
    left,
    el(
      "span",
      ctx.state.dataset?.synthetic
        ? "Dados sintéticos · Exploratório"
        : "Análise exploratória",
      "badge",
    ),
  );
  ctx.root.append(h);
}
function need(ctx, model = false) {
  if (model ? ctx.state.analysis : ctx.state.dataset) return true;
  ctx.root.append(
    empty(
      model ? "Selecione um modelo" : "Comece pelos dados",
      model
        ? "Treine um modelo ou selecione um artefato existente acima."
        : "Gere um dataset sintético ou importe um CSV no Data Explorer.",
    ),
  );
  return false;
}
function schema(state) {
  const s = state.model?.request ?? state.dataset?.column_spec ?? {};
  return Object.fromEntries(
    ["media_columns", "control_columns", "target_column", "date_column"]
      .filter((k) => s[k] !== undefined)
      .map((k) => [k, s[k]]),
  );
}
function job(ctx, text, name, args, onResult) {
  return button(
    text,
    () =>
      ctx.run(text, async () => {
        const result = await ctx.call(
          name,
          typeof args === "function" ? args() : args,
        );
        await onResult(result);
      }),
    true,
  );
}
function analysisStats(a) {
  return metrics([
    ["MAE", fmt(a.metrics.mae), "Erro absoluto no teste"],
    ["WAPE", fmt(a.metrics.wape_percent) + "%", "Erro ponderado no teste"],
    ["R²", fmt(a.metrics.r2), "Ajuste, sem inferência causal"],
    ["Períodos", String(a.evaluation.length), "Janela de avaliação"],
  ]);
}
function rawResult(p, title, data) {
  p.append(detail(title, data));
}

function overview(c) {
  head(
    c,
    "overview",
    "O desempenho do modelo, com contexto para interpretar cada resultado.",
  );
  if (!need(c)) return;
  const { state: s, root } = c;
  if (s.analysis) {
    root.append(analysisStats(s.analysis));
    const grid = el("div", "", "grid"),
      p = panel("Observado e previsto"),
      side = panel("Leitura responsável");
    p.append(
      lineChart(s.analysis.evaluation, ["observed", "predicted"], {
        label: "Observado e previsto no teste temporal",
      }),
    );
    side.append(
      el(
        "span",
        engines.find((e) => e[0] === s.backend)?.[1] ?? s.backend,
        "badge",
      ),
      el("h3", "Resultado exploratório"),
      el(
        "p",
        "Bom ajuste não demonstra que a mídia causou o resultado. Revise controles, estabilidade e evidência experimental.",
      ),
      el("p", `Dataset: ${s.datasetId}`),
      el(
        "p",
        `KPI: ${s.analysis.source.target_column} · ${s.analysis.source.frequency}`,
      ),
      detail("Diagnóstico do motor", s.analysis.diagnostic_assessment),
    );
    grid.append(p, side);
    root.append(grid);
  } else {
    root.append(
      metrics([
        ["Períodos", String(s.dataset.rows.length), "Histórico disponível"],
        [
          "Colunas",
          String(Object.keys(s.dataset.rows[0]).length),
          "Variáveis declaradas",
        ],
        [
          "Modelos",
          String(
            s.inventory.filter(
              (i) => i.model_id && i.dataset_id === s.datasetId,
            ).length,
          ),
          "Artefatos associados",
        ],
        [
          "Origem",
          s.dataset.synthetic ? "Sintética" : "Declarada",
          "Proveniência preservada",
        ],
      ]),
    );
    const p = panel("Explore antes de modelar");
    p.append(
      el(
        "p",
        "Verifique a qualidade e as definições do dataset antes de ajustar um modelo.",
      ),
      button("Ver qualidade", () => (location.hash = "quality"), true),
    );
    root.append(p);
  }
}

function data(c) {
  head(
    c,
    "data",
    "Importe dados declarados, investigue séries e preserve sua proveniência.",
  );
  const p = panel("Adicionar dataset"),
    actions = el("div", "", "actions");
  actions.append(
    job(c, "Gerar dados sintéticos", "generate_demo_dataset", {}, async (r) => {
      c.state.datasetId = r.dataset_id;
      await c.refresh();
    }),
  );
  p.append(actions);
  const imp = el("details"),
    form = el("form"),
    file = field("CSV UTF-8 (até 4 MB)", "", "file");
  file.input.accept = ".csv,text/csv";
  file.input.required = true;
  const config = jsonInput("Metadados e mapeamento explícitos", {
    synthetic: true,
    authorization_reference: "user-declared-synthetic",
    frequency: "weekly",
    source_frequency: "weekly",
    target_type: "revenue",
    delimiter: ",",
    decimal_separator: ".",
    date_column: "date",
    target_column: "revenue",
    media_columns: ["spend_search", "spend_social", "spend_video"],
    control_columns: ["price_index", "promotion"],
    column_mapping: {},
  });
  form.append(
    file.wrap,
    config.wrap,
    el(
      "p",
      "Confirme a origem nos metadados. Dados reais exigem autorização adicional no servidor. Nenhuma imputação ou ordenação é aplicada silenciosamente.",
    ),
  );
  const submit = el("button", "Importar CSV", "primary");
  form.append(submit);
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    c.run("Importando CSV", async () => {
      const f = file.input.files[0];
      if (!f || f.size > 4000000)
        throw new Error("Selecione um CSV UTF-8 com até 4 MB.");
      const csv_text = await f.text();
      const r = await c.call("import_csv", {
        ...JSON.parse(config.input.value),
        csv_text,
      });
      c.state.datasetId = r.dataset_id;
      await c.refresh();
    });
  });
  imp.append(el("summary", "Importar um arquivo CSV"), form);
  p.append(imp);
  c.root.append(p);
  if (!need(c)) return;
  const rows = c.state.dataset.rows,
    cols = Object.keys(rows[0]),
    date = cols.includes("date") ? "date" : cols[0],
    numeric = cols.filter((k) => typeof rows[0][k] === "number"),
    series = panel("Séries do dataset");
  series.append(
    lineChart(rows, numeric, {
      dateKey: date,
      label:
        "Séries do dataset nas unidades originais; selecione variáveis comparáveis",
    }),
    el(
      "p",
      "As séries mantêm suas unidades originais. Selecione variáveis compatíveis para comparar suas magnitudes.",
    ),
  );
  c.root.append(series);
  const p2 = panel("Registros"),
    filter = field("Filtrar registros por texto", ""),
    view = el("div");
  let page = 0;
  const pages = el("span");
  function draw() {
    const filtered = rows.filter((r) =>
      Object.values(r).some((v) =>
        String(v).toLowerCase().includes(filter.input.value.toLowerCase()),
      ),
    );
    const n = Math.max(1, Math.ceil(filtered.length / 50));
    page = Math.min(page, n - 1);
    view.replaceChildren(
      table(filtered.slice(page * 50, page * 50 + 50), cols),
    );
    pages.textContent = `Página ${page + 1} de ${n} · ${filtered.length} registros`;
  }
  filter.input.addEventListener("input", () => {
    page = 0;
    draw();
  });
  const pager = el("div", "", "actions");
  pager.append(
    button("Anterior", () => {
      page = Math.max(0, page - 1);
      draw();
    }),
    pages,
    button("Próxima", () => {
      page++;
      draw();
    }),
  );
  p2.append(
    filter.wrap,
    view,
    pager,
    detail(
      "Metadados e proveniência",
      Object.fromEntries(
        Object.entries(c.state.dataset).filter(
          ([k]) => k !== "rows" && k !== "provenance",
        ),
      ),
    ),
  );
  draw();
  c.root.append(p2);
}
function quality(c) {
  head(
    c,
    "quality",
    "Verifique estrutura, cobertura temporal e sinais que merecem investigação.",
  );
  if (!need(c)) return;
  const p = panel("Diagnóstico do dataset"),
    out = el("div");
  p.append(
    job(
      c,
      "Verificar qualidade",
      "data_quality",
      () => ({ dataset_id: c.state.datasetId, ...schema(c.state) }),
      (r) => {
        out.replaceChildren(
          el(
            "p",
            r.valid
              ? "Estrutura válida para os requisitos declarados."
              : "Existem problemas que impedem a modelagem.",
            "notice",
          ),
          table(
            Object.entries(r.columns).map(([name, v]) => ({ name, ...v })),
            ["name", "missing_or_invalid", "min", "max", "zero_fraction"],
          ),
          table(r.alerts, ["severity", "code", "evidence"]),
          detail("Correlações, lacunas e requisitos por motor", r),
        );
      },
    ),
    out,
  );
  c.root.append(p);
}
function modeling(c) {
  head(
    c,
    "modeling",
    "Ajuste modelos com separação temporal e premissas explícitas.",
  );
  if (!need(c)) return;
  const p = panel("Novo ajuste"),
    form = el("form"),
    engine = select("Motor estatístico", engines, "ridge"),
    config = jsonInput("Configuração do ajuste", {
      ...schema(c.state),
      test_fraction: 0.2,
      warmup_periods: 8,
      ridge_alpha: 0.1,
      adstock_decay: 0.5,
      saturation_multiplier: 1,
      bootstrap_samples: 100,
    }),
    status = el("div");
  engine.input.addEventListener("change", () => {
    config.input.value = JSON.stringify(
      engine.input.value === "ridge"
        ? {
            ...schema(c.state),
            test_fraction: 0.2,
            warmup_periods: 8,
            ridge_alpha: 0.1,
            adstock_decay: 0.5,
            bootstrap_samples: 100,
          }
        : {
            ...schema(c.state),
            test_fraction: 0.2,
            draws: 100,
            tune: 100,
            chains: 2,
          },
      null,
      2,
    );
  });
  form.append(
    engine.wrap,
    config.wrap,
    el(
      "p",
      "A execução é assíncrona na interface. O servidor permite um cálculo por vez. Ajustes curtos de MCMC servem para verificar funcionamento, não para validar inferência.",
    ),
  );
  const submit = el("button", "Treinar modelo", "primary");
  form.append(submit);
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    c.run("Treinando modelo", async () => {
      const backend = engine.input.value;
      const args = {
        ...JSON.parse(config.input.value),
        dataset_id: c.state.datasetId,
      };
      if (backend !== "ridge") args.backend = backend;
      const r = await c.call(
        backend === "ridge" ? "train_mmm" : "train_backend",
        args,
      );
      await c.refresh(
        `${backend === "ridge" ? "models" : "backend_models"}:${r.model_id}`,
      );
      location.hash = "results";
    });
  });
  p.append(
    form,
    job(c, "Consultar runtimes", "backend_status", {}, (r) =>
      status.replaceChildren(detail("Disponibilidade real no host", r)),
    ),
    status,
  );
  c.root.append(p);
}
function results(c) {
  head(
    c,
    "results",
    "Ajuste temporal, resíduos e incerteza, sem transformar associação em causalidade.",
  );
  if (!need(c, true)) return;
  const a = c.state.analysis;
  c.root.append(analysisStats(a));
  const fit = panel("Ajuste no teste temporal"),
    rows = a.evaluation.map((r, i) => ({
      ...r,
      ...(a.intervals.lower
        ? { lower: a.intervals.lower[i], upper: a.intervals.upper[i] }
        : {}),
    }));
  fit.append(
    lineChart(rows, [
      "observed",
      "predicted",
      ...(a.intervals.lower ? ["lower", "upper"] : []),
    ]),
    detail("Semântica dos intervalos", a.intervals),
  );
  const residual = panel("Resíduos no teste");
  residual.append(
    lineChart(
      a.evaluation.map((r) => ({
        date: r.date,
        residual: r.observed - r.predicted,
      })),
      ["residual"],
    ),
    el(
      "p",
      "Resíduo = observado − previsto. A inspeção visual não certifica independência dos erros.",
    ),
  );
  c.root.append(fit, residual);
  const diagnostics = panel("Diagnósticos e componentes");
  diagnostics.append(
    detail("Diagnósticos nativos e classificação", {
      assessment: a.diagnostic_assessment,
      diagnostics: a.diagnostics,
    }),
    detail("Configuração efetiva", a.effective_configuration),
  );
  if (c.state.backend === "ridge") {
    const out = el("div");
    diagnostics.append(
      job(
        c,
        "Calcular auditoria e componentes",
        "audit_model",
        { model_id: a.model_id },
        (r) =>
          out.replaceChildren(
            table(
              Object.entries(r.decomposition.component_totals).map(
                ([component, total]) => ({ component, total }),
              ),
              ["component", "total"],
            ),
            el(
              "p",
              `Erro máximo de reconciliação: ${r.decomposition.maximum_reconciliation_error}. Componentes ajustados não são efeitos causais incrementais.`,
            ),
            detail("Decomposição reconciliada, backtests e sensibilidade", r),
          ),
      ),
      out,
    );
  } else
    diagnostics.append(
      el(
        "p",
        "Decomposição unificada indisponível neste adaptador. Os diagnósticos nativos são preservados.",
      ),
    );
  c.root.append(diagnostics);
}
function comparison(c) {
  head(
    c,
    "comparison",
    "Compare o mesmo KPI e dataset em datas de teste explicitamente alinhadas.",
  );
  if (!need(c)) return;
  const p = panel("Modelos para comparar"),
    form = el("form"),
    options = [];
  for (const i of c.state.inventory.filter(
    (i) =>
      ["models", "backend_models"].includes(i.kind) &&
      i.dataset_id === c.state.datasetId,
  )) {
    const l = el("label", i.artifact_id),
      input = el("input");
    input.type = "checkbox";
    l.prepend(input);
    form.append(l);
    options.push({ i, input });
  }
  const policy = select("Janela de avaliação", [
    ["exact", "Datas idênticas"],
    ["intersection", "Interseção explícita"],
  ]);
  form.append(policy.wrap);
  const out = el("div");
  form.append(
    button(
      "Comparar modelos",
      () =>
        c.run("Comparando modelos", async () => {
          const chosen = options.filter((o) => o.input.checked);
          if (chosen.length < 2 || chosen.length > 5)
            throw new Error("Selecione de dois a cinco modelos.");
          const models = [];
          for (const { i } of chosen) {
            const backend =
              i.kind === "models"
                ? "ridge"
                : (
                    await c.call("get_backend_model", {
                      model_id: i.artifact_id,
                    })
                  ).backend;
            models.push({ model_id: i.artifact_id, backend });
          }
          const r = await c.call("compare_models", {
            models,
            window_policy: policy.input.value,
          });
          out.replaceChildren(
            table(
              r.models.map((m) => ({
                backend: m.backend,
                model_id: m.model_id,
                ...m.metrics,
              })),
              ["backend", "model_id", "mae", "wape_percent", "r2"],
            ),
            el(
              "p",
              "Não há vencedor universal. Janelas, priors, seleção e significado dos intervalos podem diferir.",
              "notice",
            ),
            detail("Comparação completa e limites", r),
          );
        }),
      true,
    ),
  );
  p.append(form, out);
  c.root.append(p);
}
function response(c) {
  head(
    c,
    "response",
    "Explore formas de resposta ajustadas e o carregamento temporal da mídia.",
  );
  if (!need(c, true)) return;
  const p = panel("Curvas condicionais");
  if (c.state.backend !== "ridge") {
    p.append(
      el(
        "p",
        "Curvas analíticas unificadas indisponíveis para este motor. Nenhuma curva Ridge substitui o resultado nativo.",
      ),
      detail("Capacidades verificadas", c.state.analysis.capabilities),
    );
    c.root.append(p);
    return;
  }
  const m = c.state.model;
  for (const channel of m.request.media_columns) {
    const par = m.media_parameters[channel],
      beta = m.coefficients[channel],
      k = par.half_saturation;
    const rows = Array.from({ length: 61 }, (_, i) => ({
      date: String(Math.round((k * 3 * i) / 60)),
      [channel]: (beta * ((k * 3 * i) / 60)) / (k + (k * 3 * i) / 60),
    }));
    const section = panel(channel);
    section.append(
      el(
        "p",
        `Meia saturação: ${fmt(k)} · Coeficiente: ${fmt(beta)} · Decaimento: ${fmt(par.decay)}`,
      ),
      el("h3", "Saturação em equilíbrio"),
      lineChart(rows, [channel], {
        label: `Resposta condicional de ${channel} em equilíbrio, gasto por período`,
      }),
      el(
        "p",
        "Equilíbrio estacionário do adstock normalizado; eixo horizontal em gasto por período. Não representa retorno causal ou uma previsão de curto prazo.",
      ),
    );
    section.append(
      el("h3", "Adstock: resposta a um impulso unitário"),
      lineChart(
        Array.from({ length: 27 }, (_, i) => ({
          date: String(i),
          [channel]: (1 - par.decay) * par.decay ** i,
        })),
        [channel],
        {
          label: `Adstock geométrico normalizado de ${channel}; períodos após impulso unitário`,
        },
      ),
      el(
        "p",
        "Peso = (1 − decaimento) × decaimento^período. É uma transformação da mídia; não é o efeito causal da campanha.",
      ),
    );
    p.append(section);
  }
  p.append(detail("Parâmetros preservados", m.media_parameters));
  c.root.append(p);
}
function simulation(c) {
  head(
    c,
    "simulation",
    "Teste alocações condicionais. Nenhuma alteração é enviada às plataformas de mídia.",
  );
  if (!need(c, true)) return;
  const p = panel("Cenário de orçamento"),
    a = c.state.analysis;
  if (c.state.backend !== "ridge") {
    p.append(
      el(
        "p",
        "O simulador de alocação plana é suportado pelo Ridge. Use uma projeção explícita quando o motor oferecer essa operação.",
      ),
      detail("Capacidades e motivos", a.capabilities),
    );
  } else {
    const m = c.state.model,
      form = el("form"),
      budget = field("Orçamento total do horizonte", 50000, "number"),
      horizon = field("Horizonte em períodos", 13, "number");
    budget.input.min = "0";
    budget.input.max = "1000000000";
    budget.input.step = "any";
    horizon.input.min = "1";
    horizon.input.max = "104";
    horizon.input.step = "1";
    form.append(budget.wrap, horizon.wrap);
    const sliders = m.request.media_columns.map((ch) => {
      const f = field(ch, 100, "range");
      f.input.min = "0";
      f.input.max = "100";
      const output = el("output", "");
      f.wrap.append(output);
      form.append(f.wrap);
      return { ch, ...f, output };
    });
    function weights() {
      const total = sliders.reduce((s, f) => s + Number(f.input.value), 0);
      sliders.forEach(
        (f) =>
          (f.output.textContent = total
            ? fmt((Number(f.input.value) / total) * 100) + "%"
            : "Sem alocação"),
      );
      return Object.fromEntries(
        sliders.map((f) => [f.ch, total ? Number(f.input.value) / total : 0]),
      );
    }
    sliders.forEach((f) => f.input.addEventListener("input", weights));
    weights();
    const out = el("div");
    form.append(
      el(
        "p",
        "Os pesos são normalizados. O gasto é plano ao longo do horizonte; controles futuros são mantidos no último valor observado, salvo declaração explícita.",
      ),
    );
    const controls = jsonInput(
        "Controles futuros opcionais (null mantém os últimos valores)",
        null,
      ),
      advanced = el("details");
    advanced.append(el("summary", "Premissas e restrições"), controls.wrap);
    const bounds = jsonInput("Limites totais por canal para otimização", {
      lower: {},
      upper: {},
    });
    advanced.append(bounds.wrap);
    form.append(advanced);
    const args = () => ({
      model_id: a.model_id,
      total_budget: Number(budget.input.value),
      horizon: Number(horizon.input.value),
      allocation: weights(),
      future_controls: JSON.parse(controls.input.value),
    });
    function show(r) {
      c.state.scenarios.push(r);
      out.replaceChildren(
        metrics([
          ["KPI projetado", fmt(r.predicted_total), "Soma no horizonte"],
          [
            "Referência",
            fmt(r.reference_predicted_total),
            "Gasto médio recente",
          ],
          ["Diferença", fmt(r.predicted_difference), "Associação condicional"],
          ["Orçamento", fmt(r.total_budget), "Total do horizonte"],
        ]),
        lineChart(r.periods, ["predicted", "reference_predicted"]),
        detail("Intervalos, premissas e alertas", r),
        button("Exportar cenário", () =>
          download(JSON.stringify(r, null, 2), "cenario.json"),
        ),
      );
      if (c.state.scenarios.length > 1)
        out.append(
          table(
            c.state.scenarios.map((s, i) => ({
              cenario: i + 1,
              orcamento: s.total_budget,
              horizonte: s.horizon,
              kpi: s.predicted_total,
            })),
            ["cenario", "orcamento", "horizonte", "kpi"],
          ),
        );
    }
    const submit = el("button", "Simular cenário", "primary");
    form.append(submit);
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      c.run("Simulando cenário", async () =>
        show(await c.call("simulate_budget", args())),
      );
    });
    form.append(
      job(
        c,
        "Calcular candidato com restrições",
        "optimize_budget",
        () => {
          const r = args();
          delete r.allocation;
          return { ...r, ...JSON.parse(bounds.input.value) };
        },
        (r) =>
          out.replaceChildren(
            el(
              "p",
              "Candidato exploratório; não é recomendação de alteração de verba.",
              "notice",
            ),
            detail("Otimização e restrições", r),
          ),
      ),
    );
    p.append(form, out);
  }
  c.root.append(p);
  if (a.capabilities.future_projection.available) {
    const f = panel("Plano futuro explícito"),
      channels = a.source.media_columns,
      config = jsonInput("Gastos e controles por período", {
        horizon: 4,
        media_plan: Object.fromEntries(
          channels.map((ch) => [ch, [1000, 1000, 1000, 1000]]),
        ),
        future_controls: Object.fromEntries(
          (a.request.control_columns ?? []).map((ch) => [ch, [0, 0, 0, 0]]),
        ),
      }),
      out = el("div");
    f.append(
      el(
        "p",
        "Exemplo de preenchimento: revise todos os valores de mídia e controles antes de executar. Não representa um plano recomendado.",
      ),
      config.wrap,
      job(
        c,
        "Projetar plano",
        "forecast_model",
        () => ({
          ...JSON.parse(config.input.value),
          model_id: a.model_id,
          backend: c.state.backend,
        }),
        (r) =>
          out.replaceChildren(
            detail("Projeção condicional e intervalos", r),
            button("Exportar projeção", () =>
              download(JSON.stringify(r, null, 2), "projecao.json"),
            ),
          ),
      ),
      out,
    );
    c.root.append(f);
  }
}
function insights(c) {
  head(
    c,
    "insights",
    "Conclusões rastreáveis e condições que limitam a tomada de decisão.",
  );
  if (!need(c, true)) return;
  const a = c.state.analysis,
    p = panel("O que os resultados permitem afirmar");
  p.append(
    el(
      "p",
      "O modelo descreve associações condicionais às variáveis e premissas utilizadas. Resultados sintéticos validam o software, não a eficácia do investimento.",
      "notice",
    ),
    el("h3", "Antes de alterar investimentos"),
    el(
      "p",
      "Investigue controles omitidos, estabilidade temporal, sensibilidade às premissas e evidência experimental. Intervalos condicionais não garantem cobertura no mercado.",
    ),
    detail("Estado de decisão e evidências", a.decision_support),
    detail("Alertas preservados do modelo", a.warnings),
    detail("Convergência e diagnósticos", a.diagnostic_assessment),
  );
  c.root.append(p);
}
function reports(c) {
  head(
    c,
    "reports",
    "Exporte evidências reproduzíveis, configurações e resultados exploratórios.",
  );
  if (!need(c, true)) return;
  const p = panel("Arquivos de análise"),
    a = c.state.analysis;
  for (const format of ["json", "csv", "markdown"])
    p.append(
      job(
        c,
        `Exportar ${format.toUpperCase()}`,
        "export_analysis",
        { model_id: a.model_id, backend: c.state.backend, format },
        (r) =>
          download(
            r.content,
            `analise.${format === "markdown" ? "md" : format}`,
            format === "json" ? "application/json" : "text/plain",
          ),
      ),
    );
  if (c.state.backend === "ridge") {
    p.append(
      job(
        c,
        "Exportar dashboard HTML offline",
        "render_dashboard",
        { model_id: a.model_id },
        (r) => download(r.content, "dashboard.html", "text/html"),
      ),
      job(
        c,
        "Gerar relatório Markdown",
        "generate_report",
        { model_id: a.model_id },
        (r) => download(r.content, "relatorio.md", "text/markdown"),
      ),
    );
  } else
    p.append(
      el(
        "p",
        "O HTML offline com simulador está disponível para Ridge. Este motor permite exportação canônica JSON, CSV e Markdown.",
      ),
    );
  p.append(
    el(
      "p",
      "O HTML offline preserva seus próprios controles locais; não executa treinamentos. Exportações podem conter dados do dataset selecionado.",
    ),
  );
  c.root.append(p);
}
export const views = {
  overview,
  data,
  quality,
  modeling,
  results,
  comparison,
  response,
  simulation,
  insights,
  reports,
};
