import { $, el } from "./ui.js";
import { MCPClient } from "./client.js";
import { views, modules } from "./views.js";

const state = {
  client: null,
  dataset: null,
  datasetId: "",
  model: null,
  analysis: null,
  backend: "ridge",
  inventory: [],
  scenarios: [],
  busy: false,
};
const systemTheme = matchMedia("(prefers-color-scheme: dark)");
function theme() {
  document.documentElement.dataset.theme =
    $("theme").value === "system"
      ? systemTheme.matches
        ? "dark"
        : "light"
      : $("theme").value;
}
$("theme").addEventListener("change", theme);
systemTheme.addEventListener("change", theme);
theme();
for (const [id, title] of modules) {
  const a = el("a");
  a.href = "#" + id;
  a.append(
    el(
      "span",
      String(modules.findIndex((m) => m[0] === id) + 1).padStart(2, "0"),
      "nav-index",
    ),
    el("span", title),
  );
  $("nav").append(a);
}
function render() {
  const id = modules.some((m) => m[0] === location.hash.slice(1))
    ? location.hash.slice(1)
    : "overview";
  $("breadcrumb").textContent = modules.find((m) => m[0] === id)[1];
  for (const a of $("nav").children) {
    a.removeAttribute("aria-current");
    if (a.hash === "#" + id) a.setAttribute("aria-current", "page");
  }
  if (!state.client) return;
  $("main").replaceChildren();
  views[id]({
    state,
    root: $("main"),
    run,
    refresh,
    loadModel,
    render,
    call: (name, args) => state.client.call(name, args),
  });
}
window.addEventListener("hashchange", () => {
  if (state.busy) return;
  render();
  $("main").focus({ preventScroll: true });
  window.scrollTo(0, 0);
});
async function run(label, action) {
  if (state.busy) return;
  state.busy = true;
  $("error").hidden = true;
  const began = Date.now();
  const progress = () => {
    $("status").textContent =
      `${label} · ${Math.floor((Date.now() - began) / 1000)} s · Aguardando resposta do servidor`;
  };
  progress();
  const timer = setInterval(progress, 1000);
  $("main").setAttribute("aria-busy", "true");
  $("nav").inert = true;
  const locked = [
    ...document.querySelectorAll(
      "#main button,#main input,#main select,#main textarea,.contextbar button,.contextbar select",
    ),
  ].filter((n) => !n.disabled);
  locked.forEach((n) => (n.disabled = true));
  try {
    await action();
    $("status").textContent = `${label} · Concluído`;
  } catch (error) {
    $("status").textContent = "";
    $("error").textContent = error.message;
    $("error").hidden = false;
  } finally {
    clearInterval(timer);
    state.busy = false;
    $("main").removeAttribute("aria-busy");
    $("nav").inert = false;
    locked.forEach((n) => (n.disabled = false));
  }
}
function option(select, value, label) {
  const o = el("option", label);
  o.value = value;
  select.append(o);
}
async function refresh(preferredModel) {
  state.inventory = (await state.client.call("storage_inventory")).artifacts;
  const datasets = state.inventory.filter((i) => i.kind === "datasets");
  if (!datasets.some((i) => i.artifact_id === state.datasetId))
    state.datasetId = datasets[0]?.artifact_id ?? "";
  $("dataset").replaceChildren();
  option($("dataset"), "", "Selecione um dataset");
  datasets.forEach((i) => option($("dataset"), i.artifact_id, i.artifact_id));
  $("dataset").value = state.datasetId;
  state.dataset = state.datasetId
    ? await state.client.dataset(state.datasetId)
    : null;
  const models = state.inventory.filter(
    (i) =>
      ["models", "backend_models"].includes(i.kind) &&
      i.dataset_id === state.datasetId,
  );
  const previous = preferredModel ?? $("model").value;
  $("model").replaceChildren();
  option($("model"), "", "Selecione um modelo");
  models.forEach((i) =>
    option(
      $("model"),
      `${i.kind}:${i.artifact_id}`,
      `${i.kind === "models" ? "Ridge" : "Nativo"} · ${i.artifact_id}`,
    ),
  );
  $("model").value = models.some(
    (i) => `${i.kind}:${i.artifact_id}` === previous,
  )
    ? previous
    : "";
  await loadModel();
  render();
}
async function loadModel() {
  state.model = null;
  state.analysis = null;
  state.scenarios = [];
  const value = $("model").value;
  if (!value) return;
  const [kind, id] = value.split(":");
  state.model = await state.client.call(
    kind === "models" ? "get_model" : "get_backend_model",
    { model_id: id },
  );
  state.backend = state.model.backend ?? "ridge";
  state.analysis = await state.client.call("get_analysis", {
    model_id: id,
    backend: state.backend,
  });
}
$("dataset").addEventListener("change", () =>
  run("Carregando dataset", async () => {
    state.datasetId = $("dataset").value;
    $("model").value = "";
    await refresh();
  }),
);
$("model").addEventListener("change", () =>
  run("Carregando modelo", async () => {
    await loadModel();
    render();
  }),
);
async function connect() {
  state.client = new MCPClient();
  state.tools = await state.client.connect();
  await refresh();
}
$("refresh").addEventListener("click", () =>
  run("Atualizando workspace", connect),
);
if (location.protocol === "file:") {
  $("error").hidden = false;
  $("error").textContent =
    "Abra pelo servidor local: execute mmm-intelligence-mcp dashboard e acesse http://127.0.0.1:8769/app. Este arquivo precisa do servidor para consultar os dados.";
} else {
  run("Abrindo workspace", connect);
}
