export const $ = (id) => document.getElementById(id);
export const fmt = (n) =>
  typeof n === "number" && Number.isFinite(n)
    ? new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 }).format(n)
    : "Indisponível";
export function el(tag, text = "", cls = "") {
  const n = document.createElement(tag);
  n.textContent = text;
  if (cls) n.className = cls;
  return n;
}
export function panel(title) {
  const n = el("section", "", "panel");
  n.append(el("h2", title));
  return n;
}
export function detail(title, data) {
  const n = el("details");
  n.append(el("summary", title), el("pre", JSON.stringify(data, null, 2)));
  return n;
}
export function button(text, action, primary = false) {
  const n = el("button", text, primary ? "primary" : "");
  n.type = "button";
  n.addEventListener("click", action);
  return n;
}
export function field(label, value, type = "text") {
  const wrap = el("label", label),
    input = el("input");
  input.type = type;
  input.value = value;
  wrap.append(input);
  return { wrap, input };
}
export function select(label, options, value) {
  const wrap = el("label", label),
    input = el("select");
  input.setAttribute("aria-label", label);
  for (const [v, t] of options) {
    const o = el("option", t);
    o.value = v;
    input.append(o);
  }
  input.value = value ?? options[0]?.[0];
  wrap.append(input);
  return { wrap, input };
}
export function jsonInput(label, value) {
  const wrap = el("label", label),
    input = el("textarea");
  input.value = JSON.stringify(value, null, 2);
  input.spellcheck = false;
  wrap.append(input);
  return { wrap, input };
}
export function download(content, name, type = "application/json") {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = el("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 3000);
}
export function table(rows, columns) {
  const wrap = el("div", "", "table-wrap"),
    t = el("table"),
    head = el("thead"),
    tr = el("tr");
  for (const c of columns) {
    const th = el("th", c.label ?? c);
    th.scope = "col";
    tr.append(th);
  }
  head.append(tr);
  t.append(head);
  const body = el("tbody");
  for (const r of rows) {
    const row = el("tr");
    for (const c of columns) {
      const v = r[c.key ?? c];
      row.append(
        el(
          "td",
          typeof v === "number"
            ? fmt(v)
            : typeof v === "object"
              ? JSON.stringify(v)
              : String(v ?? "—"),
        ),
      );
    }
    body.append(row);
  }
  t.append(body);
  wrap.append(t);
  return wrap;
}
export function metrics(values) {
  const n = el("div", "", "metrics");
  for (const [label, value, help] of values) {
    const m = el("div", "", "metric");
    m.append(el("span", label), el("strong", value), el("span", help));
    n.append(m);
  }
  return n;
}
export function empty(title, message) {
  const n = el("div", "", "empty");
  n.append(el("h2", title), el("p", message));
  return n;
}
export const engines = [
  ["ridge", "Ridge exploratório"],
  ["google_meridian", "Google Meridian"],
  ["meta_robyn", "Meta Robyn"],
  ["pymc_marketing", "PyMC-Marketing"],
];
