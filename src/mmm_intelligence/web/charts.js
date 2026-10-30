import { el, field, button, download, fmt } from "./ui.js";
const NS = "http://www.w3.org/2000/svg";
const colors = [
  "var(--search)",
  "var(--social)",
  "var(--video)",
  "#9a5d8c",
  "#607c8c",
];
function colorIndex(key, index) {
  return { spend_search: 0, spend_social: 1, spend_video: 2 }[key] ?? index;
}
function svg(tag, attrs) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
}
export function lineChart(
  rows,
  keys,
  { label = "Série temporal", dateKey = "date" } = {},
) {
  const root = el("div"),
    controls = el("div", "", "chart-controls"),
    tip = el(
      "div",
      "Passe sobre o gráfico ou use as setas do teclado.",
      "chart-tip",
    );
  tip.setAttribute("aria-live", "polite");
  const selected = new Set(keys),
    chart = svg("svg", {
      viewBox: "0 0 840 300",
      class: "chart",
      role: "img",
      tabindex: "0",
      "aria-label": label,
    });
  const zoom = el("div", "", "chart-zoom"),
    start = field("Início da janela", 0, "range"),
    end = field("Fim da janela", Math.max(0, rows.length - 1), "range");
  for (const f of [start, end]) {
    f.input.min = "0";
    f.input.max = String(Math.max(0, rows.length - 1));
    f.input.step = "1";
    zoom.append(f.wrap);
    f.input.addEventListener("input", draw);
  }
  // Range inputs clamp their initial value to the default maximum of 100.
  // Set the endpoints after applying the dataset's actual range.
  start.input.value = "0";
  end.input.value = String(Math.max(0, rows.length - 1));
  keys.forEach((k, i) => {
    const l = el("label", k, `legend-${colorIndex(k, i) % 3}`),
      c = el("input");
    c.type = "checkbox";
    c.checked = true;
    c.addEventListener("change", () => {
      c.checked ? selected.add(k) : selected.delete(k);
      draw();
    });
    l.prepend(c);
    controls.append(l);
  });
  controls.append(
    button("Exportar série CSV", () => {
      const cols = [dateKey, ...keys];
      const quote = (v) => '"' + String(v ?? "").replaceAll('"', '""') + '"';
      download(
        [cols, ...rows.map((r) => cols.map((k) => r[k]))]
          .map((r) => r.map(quote).join(","))
          .join("\n"),
        "serie.csv",
        "text/csv",
      );
    }),
  );
  let windowRows = [],
    cursor = 0;
  function inspect(index) {
    cursor = Math.max(0, Math.min(windowRows.length - 1, index));
    const r = windowRows[cursor];
    if (r)
      tip.textContent = `${r[dateKey]} · ${[...selected].map((k) => `${k}: ${fmt(r[k])}`).join(" · ")}`;
  }
  function draw() {
    chart.replaceChildren();
    const lo = Math.min(+start.input.value, +end.input.value),
      hi = Math.max(+start.input.value, +end.input.value);
    windowRows = rows.slice(lo, hi + 1);
    const vals = windowRows
      .flatMap((r) => [...selected].map((k) => r[k]))
      .filter(Number.isFinite);
    if (!vals.length) {
      tip.textContent = "Sem valores na seleção.";
      return;
    }
    let min = vals.reduce((a, b) => Math.min(a, b), Infinity),
      max = vals.reduce((a, b) => Math.max(a, b), -Infinity);
    if (min === max) {
      min -= 1;
      max += 1;
    }
    const x = (i) => 64 + (i * 744) / Math.max(1, windowRows.length - 1),
      y = (v) => 250 - ((v - min) * 220) / (max - min);
    for (let i = 0; i < 5; i++) {
      const v = min + ((max - min) * i) / 4;
      chart.append(
        svg("line", {
          x1: 64,
          x2: 808,
          y1: y(v),
          y2: y(v),
          class: "chart-grid",
        }),
      );
      const t = svg("text", { x: 54, y: y(v) + 4, "text-anchor": "end" });
      t.textContent = new Intl.NumberFormat("pt-BR", {
        notation: "compact",
        maximumFractionDigits: 1,
      }).format(v);
      chart.append(t);
    }
    keys.forEach((k, i) => {
      if (!selected.has(k)) return;
      let pen = false;
      const d = windowRows
        .map((r, j) => {
          if (!Number.isFinite(r[k])) {
            pen = false;
            return "";
          }
          const op = pen ? "L" : "M";
          pen = true;
          return `${op}${x(j)},${y(r[k])}`;
        })
        .join(" ");
      chart.append(
        svg("path", {
          d,
          fill: "none",
          stroke: colors[colorIndex(k, i) % colors.length],
          "stroke-width": 2.5,
          "stroke-dasharray": i > 0 ? "6 3" : "none",
        }),
      );
    });
    for (const [i, anchor] of [
      [0, "start"],
      [windowRows.length - 1, "end"],
    ]) {
      const t = svg("text", { x: x(i), y: 282, "text-anchor": anchor });
      t.textContent = windowRows[i]?.[dateKey] ?? "";
      chart.append(t);
    }
    inspect(cursor);
  }
  chart.addEventListener("pointermove", (e) => {
    const b = chart.getBoundingClientRect();
    inspect(
      Math.round(
        ((((e.clientX - b.left) * 840) / b.width - 64) / 744) *
          (windowRows.length - 1),
      ),
    );
  });
  chart.addEventListener("keydown", (e) => {
    if (["ArrowLeft", "ArrowRight"].includes(e.key)) {
      e.preventDefault();
      inspect(cursor + (e.key === "ArrowRight" ? 1 : -1));
    }
  });
  root.append(controls, chart, tip, zoom);
  draw();
  return root;
}
