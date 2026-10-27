# V4.2 — validação incremental

Dados usados: exclusivamente sintéticos. Ambiente local Windows / Python 3.12 / Chrome. O teste web inicia servidor e armazenamento temporários, sem login, token, cookies ou alteração de campanhas.

- [Resultado estruturado do navegador](browser.json): chamadas reais, igualdade numérica, cinco larguras e axe-core claro/escuro.
- [Antes: relatório offline V4](before-offline.png).
- [Workspace claro](dashboard-light.png), [escuro](dashboard-dark.png) e [mobile](dashboard-mobile.png).
- [Resumo dos checks](checks.json).

O scanner automático não equivale a certificação WCAG. Não foram repetidos os ajustes nativos longos nem as auditorias científicas V4. O novo recurso MCP de leitura de datasets foi testado sob isolamento de tenant. Testes verificam que `/mcp` segue retornando 401 sem credenciais e que `/app/mcp` recusa origens externas, clientes não loopback e cabeçalhos de proxy.

O plugin local foi testado como subprocesso fora do checkout, com 26 ferramentas descobertas e geração/validação de dados. Isso não equivale à instalação no host ChatGPT/Codex ou aprovação no diretório. Os arquivos de deploy têm verificações estruturais; não houve execução Docker, TLS público ou OAuth.
