/** Same-origin local dashboard bridge. The separate /mcp endpoint keeps bearer auth. */
export class MCPClient {
  #id = 0;
  async rpc(method, params = {}) {
    const response = await fetch("/app/mcp", {
      method: "POST",
      cache: "no-store",
      credentials: "omit",
      headers: {
        "X-MMM-Dashboard": "1",
        "Content-Type": "application/json",
        Accept: "application/json, text/event-stream",
        "MCP-Protocol-Version": "2025-11-25",
      },
      body: JSON.stringify({ jsonrpc: "2.0", id: ++this.#id, method, params }),
    });
    if (!response.ok)
      throw new Error(
        `Servidor HTTP ${response.status}${response.status === 429 ? " — aguarde antes de repetir" : ""}`,
      );
    const message = await response.json();
    if (message.error)
      throw new Error(message.error.message || "Falha no protocolo MCP");
    return message.result;
  }
  async connect() {
    await this.rpc("initialize", {
      protocolVersion: "2025-11-25",
      capabilities: {},
      clientInfo: { name: "mmm-workspace", version: "0.4.2" },
    });
    return (await this.rpc("tools/list")).tools;
  }
  async call(name, request = {}) {
    const result = await this.rpc("tools/call", {
      name,
      arguments: { request },
    });
    const payload = result.structuredContent;
    if (result.isError || !payload?.ok)
      throw new Error(
        payload?.error
          ? `${payload.error.code}: ${payload.error.message}`
          : result.content?.[0]?.text || "Resposta MCP inválida",
      );
    return payload.data;
  }
  async dataset(id) {
    const result = await this.rpc("resources/read", {
      uri: `mmm://datasets/${encodeURIComponent(id)}`,
    });
    return JSON.parse(result.contents[0].text);
  }
}
