import {
  el,
  panel,
  field,
  select,
  jsonInput,
  button,
  detail,
  table,
  download,
  empty,
} from "./ui.js";
import { lineChart } from "./charts.js";

export const growthModules = [
  ["ingest-files", "Importar arquivos"],
  ["growth-datasets", "Acervo e procedência"],
  ["media-quality", "Validação de mídia"],
  ["combine", "Combinar fontes"],
  ["growth-analysis", "Growth e coortes"],
  ["mmm-prepare", "Preparar MMM"],
  ["experiments", "Decisões e experimentos"],
  ["growth-reports", "Relatórios de Growth"],
];
const state = (c) =>
  (c.state.growth ??= {
    results: {},
    forms: {},
    artifacts: [],
    profiles: [],
    source: "",
    normalized: "",
    plan: "",
    decision: "",
  });
const id = (c, kind = "normalized") => state(c)[kind] || "";
const input = (key, label, value, kind = "text", options = null) => ({
  key,
  label,
  value,
  kind,
  options,
});
function header(c, title, text) {
  c.root.append(el("h1", title), el("p", text));
}
function remember(c, tool, data) {
  const g = state(c);
  g.results[tool] = data;
  if (data.artifact_type === "source") g.source = data.artifact_id;
  if (data.artifact_type === "normalized") g.normalized = data.artifact_id;
  if (data.artifact_type === "experiment_plan") g.plan = data.artifact_id;
  if (data.artifact_type === "decision") g.decision = data.artifact_id;
}
function show(c, container, tool, data) {
  remember(c, tool, data);
  container.replaceChildren(
    detail("Resultado, procedência e limitações", data),
  );
  if (data.coverage_matrix)
    container.prepend(
      table(data.coverage_matrix, [
        "artifact_id",
        "channel_confirmed",
        "status",
        "dataset_applicability",
        "row_count",
        "period",
        "warnings",
      ]),
    );
  if (data.groups)
    for (const group of data.groups)
      for (const [name, metric] of Object.entries(group.metrics)) {
        if (metric.dates)
          container.append(
            lineChart(
              metric.dates.map((date, i) => ({
                date,
                [name]: metric.values[i],
              })),
              [name],
              { label: `${name} · ${JSON.stringify(group.segment)}` },
            ),
          );
      }
  container.append(
    button("Exportar este resultado", () =>
      download(JSON.stringify(data, null, 2), `${tool}.json`),
    ),
  );
}
function operation(
  c,
  title,
  tool,
  fields,
  label,
  extra = () => ({}),
  after = null,
) {
  const g = state(c),
    p = panel(title),
    form = el("div", "", "form-grid"),
    out = el("div"),
    controls = [];
  for (const spec of fields) {
    const draft = g.forms[`${tool}.${spec.key}`];
    const value =
      draft ?? (typeof spec.value === "function" ? spec.value() : spec.value);
    const control =
      spec.kind === "json"
        ? jsonInput(spec.label, value)
        : spec.kind === "select"
          ? select(spec.label, spec.options, value)
          : field(
              spec.label,
              value,
              spec.kind === "optional" ? "text" : spec.kind,
            );
    if (spec.kind === "json" && draft !== undefined)
      control.input.value = draft;
    control.input.addEventListener("input", () => {
      g.forms[`${tool}.${spec.key}`] = control.input.value;
    });
    controls.push({ spec, control });
    form.append(control.wrap);
  }
  p.append(
    form,
    button(
      label,
      () =>
        c.run(label, async () => {
          const request = { ...extra() };
          for (const { spec, control } of controls) {
            const value = control.input.value;
            request[spec.key] =
              spec.kind === "optional"
                ? value.trim() || null
                : spec.kind === "json"
                  ? JSON.parse(value)
                  : spec.kind === "number"
                    ? Number(value)
                    : value;
          }
          const data = await c.call(tool, request);
          show(c, out, tool, data);
          if (after) await after(data, request);
        }),
      true,
    ),
    out,
  );
  if (g.results[tool]) show(c, out, tool, g.results[tool]);
  c.root.append(p);
  return p;
}
const artifactField = (c, kind = "normalized") =>
  input("artifact_id", "ID do artefato selecionado", () => id(c, kind));

function ingestion(c) {
  const g = state(c);
  header(
    c,
    "Importar arquivos",
    "Revise o arquivo e suas definições antes de confirmar. Arquivos maiores que 2 MiB devem usar o cliente MCP local.",
  );
  const p = panel("Arquivo e interpretação"),
    out = el("div");
  const file = field("Arquivo fornecido", "", "file");
  file.input.accept = ".csv,.tsv,.json,.jsonl,.ndjson,.xlsx,.xls,.parquet,.xml";
  const format = select(
    "Formato declarado",
    ["csv", "tsv", "json", "jsonl", "xlsx", "xls", "parquet", "xml"].map(
      (x) => [x, x.toUpperCase()],
    ),
  );
  const origin = field("Origem declarada", "Arquivo fornecido pelo usuário");
  const synthetic = field(
    "Este arquivo contém somente dados sintéticos",
    "",
    "checkbox",
  );
  synthetic.input.checked = false;
  const authorization = field("Referência de autorização para dados reais", "");
  const sheet = field("Aba da planilha (quando necessária)", "");
  const delimiter = field("Delimitador opcional", "");
  const headerRow = field("Linha do cabeçalho", 1, "number");
  headerRow.input.min = "1";
  headerRow.input.max = "100";
  const encoding = select(
    "Codificação",
    ["utf-8-sig", "utf-8", "cp1252", "latin-1"].map((x) => [x, x]),
  );
  const record = field("Elemento de registro XML", "record");
  const xmlFields = jsonInput("Campos e caminhos XML", {});
  let reviewed = null;
  const confirm = button(
    "Confirmar importação do original",
    () =>
      c.run("Importando original", async () => {
        if (!reviewed)
          throw new Error("Pré-visualize novamente após alterar as opções.");
        const data = await c.call("import_source", {
          ...reviewed,
          confirm: true,
        });
        remember(c, "import_source", data);
        g.profiles = (await c.call("list_media_profiles")).profiles;
        g.artifacts = (await c.call("storage_inventory")).artifacts.filter(
          (x) => x.artifact_type,
        );
        c.render();
      }),
    true,
  );
  confirm.disabled = true;
  const options = [
    file,
    format,
    origin,
    synthetic,
    authorization,
    sheet,
    delimiter,
    headerRow,
    encoding,
    record,
    xmlFields,
  ];
  for (const option of options) {
    p.append(option.wrap);
    option.input.addEventListener("input", () => {
      reviewed = null;
      confirm.disabled = true;
    });
  }
  p.append(
    button(
      "Pré-visualizar arquivo",
      () =>
        c.run("Inspecionando arquivo", async () => {
          const selected = file.input.files[0];
          if (!selected) throw new Error("Selecione um arquivo.");
          if (selected.size > 2 * 1024 * 1024)
            throw new Error(
              "Limite da interface: 2 MiB. Use MCP stdio para arquivos maiores.",
            );
          const content = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result).split(",")[1]);
            reader.onerror = () =>
              reject(new Error("Não foi possível ler o arquivo."));
            reader.readAsDataURL(selected);
          });
          const request = {
            content_base64: content,
            format: format.input.value,
            origin: origin.input.value,
            synthetic: synthetic.input.checked,
            encoding: encoding.input.value,
            header_row: Number(headerRow.input.value),
          };
          if (sheet.input.value) request.sheet = sheet.input.value;
          if (delimiter.input.value) request.delimiter = delimiter.input.value;
          if (authorization.input.value)
            request.authorization_reference = authorization.input.value;
          if (format.input.value === "xml") {
            request.xml_record = record.input.value;
            request.xml_fields = JSON.parse(xmlFields.input.value);
          }
          const data = await c.call("preview_dataset", request);
          reviewed = request;
          confirm.disabled = false;
          out.replaceChildren(
            table(data.preview, data.columns),
            detail("Schema, abas e integridade", data),
          );
        }),
      true,
    ),
    confirm,
    out,
  );
  c.root.append(p);
  if (g.source) c.root.append(el("p", `Original confirmado: ${g.source}`));
  operation(
    c,
    "Mapeamento explícito",
    "map_dataset_schema",
    [
      input("source_id", "ID do original", () => id(c, "source")),
      input(
        "profile",
        "Perfil de mídia",
        "website",
        "select",
        g.profiles.length
          ? g.profiles.map((p) => [
              p.artifact_id ?? p.name,
              `${p.name} · v${p.version}`,
            ])
          : [["website", "website (carregue os demais perfis)"]],
      ),
      input("mapping", "Mapeamento de colunas", {}, "json"),
      input("units", "Unidades declaradas", {}, "json"),
      input("dimensions", "Dimensões e metodologia", {}, "json"),
      input("frequency_days", "Dias por período", 7, "number"),
      input("date_format", "Formato das datas", "%Y-%m-%d"),
      input("timezone", "Fuso de referência", "UTC"),
    ],
    "Normalizar arquivo",
    () => ({}),
    async (data) => {
      g.normalized = data.artifact_id;
      g.artifacts = (await c.call("storage_inventory")).artifacts.filter(
        (x) => x.artifact_type,
      );
    },
  );
  c.root.append(
    button("Carregar perfis disponíveis", () =>
      c.run("Carregando perfis", async () => {
        g.profiles = (await c.call("list_media_profiles")).profiles;
        c.render();
      }),
    ),
  );
}
function catalog(c) {
  const g = state(c);
  header(
    c,
    "Acervo e procedência",
    "Originais, versões normalizadas e resultados permanecem como artefatos separados.",
  );
  const out = el("div");
  c.root.append(
    button("Atualizar acervo", () =>
      c.run("Consultando acervo", async () => {
        g.artifacts = (await c.call("storage_inventory")).artifacts.filter(
          (x) => x.artifact_type,
        );
        c.render();
      }),
    ),
    out,
  );
  if (!g.artifacts.length)
    out.append(
      empty("Acervo vazio", "Importe um arquivo ou atualize o inventário."),
    );
  else
    out.append(
      table(g.artifacts, [
        "artifact_id",
        "artifact_type",
        "format",
        "origin",
        "synthetic",
        "sha256",
        "source_ids",
      ]),
    );
  operation(
    c,
    "Consultar versão",
    "get_growth_artifact",
    [artifactField(c)],
    "Consultar artefato",
  );
}
function quality(c) {
  header(
    c,
    "Validação de mídia",
    "Aplicabilidade e qualidade são avaliadas separadamente. Métricas incompatíveis não são somadas.",
  );
  operation(
    c,
    "Qualidade da fonte",
    "validate_media_dataset",
    [artifactField(c)],
    "Validar mídia selecionada",
  );
  operation(
    c,
    "Cobertura entre fontes",
    "validate_crossmedia_dataset",
    [
      input(
        "artifact_ids",
        "IDs normalizados para comparação",
        () => [id(c)],
        "json",
      ),
    ],
    "Validar cobertura crossmedia",
  );
  operation(
    c,
    "Perfil personalizado",
    "register_media_profile",
    [
      input("name", "Nome do perfil", "custom_channel"),
      input("version", "Versão do perfil", "1"),
      input("family", "Família", "custom"),
      input("required", "Campos obrigatórios", ["date"], "json"),
      input("optional", "Campos opcionais", [], "json"),
      input("expected_units", "Unidades esperadas", {}, "json"),
      input("nonadditive", "Métricas não aditivas", ["reach", "users"], "json"),
    ],
    "Registrar perfil imutável",
  );
}
function joins(c) {
  header(
    c,
    "Combinar fontes",
    "Escolha as chaves e revise cardinalidade, perdas e riscos antes de materializar.",
  );
  const g = state(c),
    fields = [
      input("left_id", "ID da fonte esquerda", () => id(c)),
      input("right_id", "ID da fonte direita", ""),
      input("keys", "Chaves esquerda → direita", { date: "date" }, "json"),
      input(
        "how",
        "Tipo de join",
        "inner",
        "select",
        ["inner", "left", "right", "full"].map((x) => [x, x]),
      ),
      input(
        "cardinality",
        "Cardinalidade declarada",
        "1:1",
        "select",
        ["1:1", "1:m", "m:1", "m:m"].map((x) => [x, x]),
      ),
      input(
        "frequency",
        "Alinhamento temporal",
        "original",
        "select",
        ["original", "daily", "weekly"].map((x) => [x, x]),
      ),
      input("left_aggregations", "Pré-agregação esquerda", {}, "json"),
      input("right_aggregations", "Pré-agregação direita", {}, "json"),
      input("context", "Resolução de contexto", {}, "json"),
      input("unmatched", "Sem correspondência", "allow", "select", [
        ["allow", "Preservar como desconhecido"],
        ["error", "Bloquear"],
      ]),
    ];
  let reviewed = null;
  const confirm = button(
    "Materializar join revisado",
    () =>
      c.run("Materializando join", async () => {
        if (!reviewed) throw new Error("Revise a prévia primeiro.");
        const data = await c.call("join_datasets", {
          ...reviewed,
          confirm: true,
        });
        remember(c, "join_datasets", data);
        g.normalized = data.artifact_id;
        c.render();
      }),
    true,
  );
  confirm.disabled = true;
  const p = operation(
    c,
    "Prévia de relacionamento",
    "join_datasets",
    fields,
    "Pré-visualizar join",
    () => ({ confirm: false }),
    async (data, request) => {
      reviewed = data.blocked ? null : request;
      confirm.disabled = !reviewed;
    },
  );
  p.addEventListener("input", () => {
    reviewed = null;
    confirm.disabled = true;
  });
  p.append(confirm);
}
function analytics(c) {
  header(
    c,
    "Growth e coortes",
    "Tendências são descritivas. Coortes usam denominadores de acompanhamento completo e suprimem células pequenas.",
  );
  operation(
    c,
    "Evolução temporal",
    "analyze_growth",
    [
      artifactField(c),
      input("metrics", "Métricas para análise", ["sales"], "json"),
      input("group_by", "Dimensões de segmentação", [], "json"),
      input("rolling_window", "Janela móvel", 4, "number"),
    ],
    "Analisar evolução",
  );
  operation(
    c,
    "Retenção e conversão por coorte",
    "analyze_cohorts",
    [
      artifactField(c, "source"),
      input("unit_column", "Coluna da unidade", "unit"),
      input("event_column", "Coluna do evento", "event"),
      input("date_column", "Coluna da data", "date"),
      input("entry_event", "Evento de entrada", "entry"),
      input("return_event", "Evento de retorno", "return"),
      input("as_of", "Dados completos até", "2026-01-31", "date"),
      input("horizon", "Períodos de acompanhamento", 12, "number"),
      input("frequency_days", "Dias por acompanhamento", 7, "number"),
      input("group_by", "Dimensões de coorte", [], "json"),
      input(
        "population_column",
        "Coluna de elegibilidade da coorte",
        "",
        "optional",
      ),
      input(
        "population_value",
        "Valor elegível na entrada da coorte",
        "",
        "optional",
      ),
    ],
    "Analisar coortes",
  );
  operation(
    c,
    "Diagnóstico rastreável",
    "create_growth_diagnostic",
    [artifactField(c)],
    "Criar diagnóstico",
  );
}
function preparation(c) {
  header(
    c,
    "Preparar MMM",
    "Selecione o desfecho, gastos e controles. O formato é validado contra o contrato do motor.",
  );
  const fields = [
    artifactField(c),
    input(
      "backend",
      "Motor",
      "ridge",
      "select",
      ["ridge", "google_meridian", "pymc_marketing", "meta_robyn"].map((x) => [
        x,
        x,
      ]),
    ),
    input("kpi", "KPI", "revenue"),
    input("media", "Colunas de gastos", ["spend_search"], "json"),
    input("controls", "Colunas de controle", [], "json"),
    input("target_type", "Tipo de KPI", "revenue", "select", [
      ["revenue", "Receita"],
      ["non_revenue", "Não monetário"],
    ]),
  ];
  operation(
    c,
    "Elegibilidade do desenho",
    "check_mmm_eligibility",
    fields,
    "Verificar elegibilidade MMM",
  );
  operation(
    c,
    "Materialização para treino",
    "prepare_mmm_dataset",
    [
      ...fields,
      input(
        "currency",
        "Moeda comum",
        "BRL",
        "select",
        ["BRL", "USD", "EUR", "GBP"].map((x) => [x, x]),
      ),
    ],
    "Preparar dataset de treino",
    () => ({}),
    async (data) => {
      state(c).prepared = data;
      c.render();
    },
  );
  const prepared = state(c).prepared;
  if (prepared)
    c.root.append(
      button("Treinar dataset preparado", () =>
        c.run("Treinando dataset preparado", async () => {
          const data = await c.call(
            prepared.training_tool,
            prepared.training_request,
          );
          remember(c, prepared.training_tool, data);
          await c.refresh();
        }),
      ),
    );
}
function experiments(c) {
  header(
    c,
    "Decisões e experimentos",
    "Revise hipóteses e registre os resultados fornecidos. Os métodos não executam ações em plataformas.",
  );
  const g = state(c);
  operation(
    c,
    "Proposta de decisão",
    "create_growth_decision",
    [
      input(
        "diagnostic_id",
        "ID do diagnóstico",
        () => g.results.create_growth_diagnostic?.artifact_id || "",
      ),
      input("problem", "Problema", ""),
      input("hypothesis", "Hipótese falsificável", ""),
      input("action", "Ação proposta", ""),
      input("kpi", "KPI da decisão", ""),
      input("guardrails", "Métricas de proteção", [], "json"),
      input("baseline", "Período de baseline", ""),
      input("horizon", "Horizonte esperado", ""),
      input(
        "method",
        "Método da decisão",
        "observational",
        "select",
        [
          "randomized",
          "geographic",
          "observational",
          "before_after",
          "mmm_calibration",
        ].map((x) => [x, x]),
      ),
      input("risks", "Riscos conhecidos", [], "json"),
    ],
    "Registrar proposta",
  );
  operation(
    c,
    "Revisão e histórico",
    "transition_growth_decision",
    [
      artifactField(c, "decision"),
      input(
        "state",
        "Próximo estado",
        "approved",
        "select",
        ["approved", "rejected", "planned", "evaluated", "learned"].map((x) => [
          x,
          x,
        ]),
      ),
      input("actor", "Responsável declarado", ""),
      input("note", "Parecer e limitações", ""),
      input("plan", "Plano (somente na etapa planned)", null, "json"),
      input(
        "results_id",
        "ID dos resultados (somente evaluated)",
        null,
        "json",
      ),
    ],
    "Registrar transição",
  );
  operation(
    c,
    "Planejamento estatístico",
    "plan_experiment",
    [
      input(
        "method",
        "Desenho experimental",
        "randomized",
        "select",
        [
          "randomized",
          "geographic",
          "observational",
          "before_after",
          "mmm_calibration",
        ].map((x) => [x, x]),
      ),
      input("outcome_type", "Tipo de desfecho", "binary", "select", [
        ["binary", "Binário"],
        ["continuous", "Contínuo"],
      ]),
      input("kpi", "Coluna do desfecho", "outcome"),
      input("unit_column", "Unidade independente", "unit"),
      input("group_column", "Coluna dos grupos", "arm"),
      input("treatment", "Grupo tratamento", "treatment"),
      input("control", "Grupo controle", "control"),
      input("baseline", "Baseline declarado", 0.2, "number"),
      input("minimum_effect", "Efeito mínimo relevante", 0.1, "number"),
      input("standard_deviation", "Desvio padrão (contínuo)", null, "json"),
      input("alpha", "Significância", 0.05, "number"),
      input("power", "Poder desejado", 0.8, "number"),
      input("population", "População elegível", ""),
      input("measurement_window", "Janela de mensuração", ""),
      input("stop_rule", "Regra de parada", ""),
      input("guardrails", "Guardrails planejados", [], "json"),
      input("hypothesis", "Hipótese do plano estatístico", "", "optional"),
      input("analysis_plan", "Plano de análise declarado", "", "optional"),
      input(
        "randomization_unit",
        "Coluna da unidade de randomização",
        "",
        "optional",
      ),
      input("duration_days", "Duração em dias (número ou null)", null, "json"),
      input(
        "conversion_window_days",
        "Janela de conversão em dias (número ou null)",
        null,
        "json",
      ),
      input(
        "observation_start",
        "Início verificável (AAAA-MM-DD)",
        "",
        "optional",
      ),
      input("observation_end", "Fim verificável (AAAA-MM-DD)", "", "optional"),
      input("date_column", "Coluna da data observada", "", "optional"),
      input("population_column", "Coluna de elegibilidade", "", "optional"),
      input("population_value", "Valor elegível dessa coluna", "", "optional"),
      input(
        "exclusion_criteria",
        "Critérios de exclusão declarados",
        "",
        "optional",
      ),
      input(
        "operational_constraints",
        "Restrições operacionais",
        "",
        "optional",
      ),
      input(
        "comparison_family_size",
        "Tamanho da família de comparações",
        1,
        "number",
      ),
      input(
        "guardrail_specs",
        "Desfechos, direção adversa e limiar das proteções",
        {},
        "json",
      ),
      input(
        "cost_column",
        "Coluna de custo por unidade (opcional)",
        "",
        "optional",
      ),
    ],
    "Planejar experimento",
  );
  operation(
    c,
    "Análise dos resultados importados",
    "analyze_experiment",
    [
      artifactField(c, "source"),
      input("plan_id", "ID do plano estatístico", () => id(c, "plan")),
    ],
    "Analisar experimento",
  );
}
function reports(c) {
  header(
    c,
    "Relatórios de Growth",
    "Consulte versões persistidas e exporte evidências com suas ressalvas.",
  );
  for (const [tool, data] of Object.entries(state(c).results)) {
    const p = panel(tool.replaceAll("_", " "));
    show(c, p, tool, data);
    c.root.append(p);
  }
  operation(
    c,
    "Recuperar relatório ou artefato",
    "get_growth_artifact",
    [artifactField(c)],
    "Recuperar resultado persistido",
  );
}
export const growthViews = {
  "ingest-files": ingestion,
  "growth-datasets": catalog,
  "media-quality": quality,
  combine: joins,
  "growth-analysis": analytics,
  "mmm-prepare": preparation,
  experiments,
  "growth-reports": reports,
};
