// Acceptance gate: do not round 99.99 to 100 or omit unloaded production files.
import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import { resolve } from "node:path";
const report = JSON.parse(
  await readFile(
    resolve("evidence/javascript-coverage/dashboard/coverage-summary.json"),
    "utf8",
  ),
);
const sources = (await readdir(resolve("src/mmm_intelligence/web"))).filter(
  (name) => name.endsWith(".js"),
);
for (const source of sources) {
  assert.ok(
    Object.keys(report).some(
      (key) => key.endsWith("/" + source) || key.endsWith("\\" + source),
    ),
    `Coverage missing for ${source}`,
  );
}
for (const metric of ["lines", "branches"]) {
  const measured = report.total[metric];
  assert.equal(
    measured.covered,
    measured.total,
    `${metric}: ${measured.covered}/${measured.total}; 100% required`,
  );
  assert.equal(
    measured.skipped,
    0,
    `${metric}: excluded production code requires explicit review`,
  );
}
console.log(
  "JavaScript: 100% executable lines and branches across all production assets",
);
