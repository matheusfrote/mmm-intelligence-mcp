# Plugin preparation — V4.2

Prepared: portable Agent Plugins 1.0 `plugin.json` and `mcp.json`, one domain workflow skill, icon, Apache-2.0 notices, bundled Python source and deterministic ZIP builder. The executable connection is **local stdio**. `python` must resolve to an environment containing the project dependencies; the package never installs them automatically. No global Codex configuration or account was modified.

Official references inspected on 2026-10-27: [Package your plugin](https://developers.openai.com/plugins/build/plugins) and its public-submission requirements. This format separates portable manifests from OpenAI presentation metadata. A local subprocess is not available in ChatGPT web. The public upload requires a real HTTPS endpoint; the existing fixed bearer flow is not OAuth and cannot be relabeled as such.

## Readiness

| Item | State |
|---|---|
| Local source package / reproducible ZIP | Implemented and checked by `tests/test_plugin_package.py` |
| Bundled server startup and MCP discovery | Recorded separately in validation evidence |
| Local installation inside Codex/ChatGPT | Not performed |
| Public submission ZIP | Not ready: no authorized HTTPS endpoint or supported public authentication |
| Remote infrastructure | Templates only; no Docker/TLS deployment validation |
| Publisher listing | Draft derived from implemented behavior; verified identity and countries still needed |
| Privacy/terms/support URLs | No invented URLs or commitments; publication review remains pending |
| Recorded reviewer demo / reviewer account | Not produced; no registered remote development connection |
| Directory submission / approval | Neither requested nor performed |

The earlier GitHub-only decision remains in force. These gaps do not prevent local use, packaging or tests. Public packaging stops before inserting a fake endpoint, silently dropping the server or labeling the local archive submission-ready.

## Draft review cases

Positive: (1) generate and validate synthetic weekly data; (2) inspect data quality and explain specific warnings; (3) fit Ridge and reconcile displayed MAE/WAPE/R² with held-out results; (4) compare compatible models on explicitly selected dates without naming a universal winner; (5) simulate a declared total/horizon and export the conditional result without changing campaigns.

Negative: (1) refuse a request to alter live campaign budgets because no such tool exists; (2) decline causal ROI certification from synthetic/observational fit; (3) explain unavailable native operations instead of silently using Ridge. These are draft conversational review cases, **not claims of executed host-level agent evaluations**. Protocol, software and browser tests are separate evidence.
