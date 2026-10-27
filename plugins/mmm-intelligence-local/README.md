# MMM Intelligence — local authoring package

This is a **local stdio plugin**, not a submission-ready public plugin. The built ZIP includes the Python source, Apache-2.0 notices, MCP manifest and workflow skill. Install the project Python dependencies in an isolated environment first; select that environment's Python in `mcp.json` if it is not the `python` on the host PATH. No dependency installer, lifecycle hook or account mutation runs on installation.

The launcher uses `MMM_DATA_DIR` when supplied, otherwise `~/.mmm-intelligence/plugin-data`. Data is stored locally and persists across runs. Optional Meridian, PyMC and Robyn runtimes require separate installation. Stdio has the permissions of the local process. The dashboard and authenticated HTTP MCP are separate launch modes documented in the main repository.

Build with `python examples/build_plugin.py`. This archive can be inspected or installed using a supported local plugin flow. It has not been installed in ChatGPT/Codex or submitted/approved in the public directory during this delivery. A local Python process is not accessible from ChatGPT web.

Public preparation requires a verified HTTPS MCP endpoint, a supported authentication flow, reviewed listing/policy URLs, publisher identity, intended countries, reviewer access and a recorded demo. No endpoint or app identifier is invented in this package.
