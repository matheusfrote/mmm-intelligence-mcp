# Entrega incremental V4.2

**Dashboard local sem login**, conforme a correção solicitada. Execute `mmm-intelligence-mcp dashboard` e abra `http://127.0.0.1:8769/app`. Nesta sessão, a demonstração está em `http://127.0.0.1:8772/app`. O comando roda até ser encerrado; não foi instalado como serviço do sistema.

Implementados os dez módulos, sidebar responsiva, temas claro/escuro, gráficos com seleção/janela/leitura por teclado, importação CSV, qualidade, modelagem, resultados, comparação, curvas de saturação/adstock, simulação/otimização condicionais, insights e exports. O HTML offline anterior foi preservado. A aplicação usa JavaScript modular, CSS e SVG locais; não exige Node em produção nem adiciona framework ao backend.

O workspace local acessa sua própria raiz. `/mcp` continua exigindo bearer; usuários autenticados mantêm raízes separadas. A nova ponte `/app/mcp` exige loopback e mesma origem. Não há token embutido no frontend nem armazenamento de credenciais no navegador. Não exponha a interface por proxy.

Preparados o [plugin local](../plugins/mmm-intelligence-local/README.md), ZIP determinístico e [templates de deploy](../deploy/README.md). O plugin não foi instalado no host nem submetido ao diretório; o pacote local não é um ZIP pronto para submissão pública. HTTPS público, OAuth, políticas publicadas, identidade verificada e gravação de revisão permanecem pendentes de infraestrutura e decisões do proprietário.

[Guia de uso](dashboard.md) · [Evidências e screenshots](validation/v42/README.md) · [Distribuição do plugin e limites](plugin-distribution.md).

Verificação final: **195 testes Python aprovados**, um aviso SciPy preexistente; **um cenário E2E Chrome aprovado** com 24 chamadas MCP e cinco viewports; nenhum achado axe nos dois temas da visão geral. Ruff, formatação, mypy (32 módulos), Bandit e busca de padrões de segredo passaram. ZIP local em `dist/mmm-intelligence-local-0.1.0.zip`; SHA-256 no resumo de checks.

Alterações anteriores da branch `feat/v4-intelligence` preservadas. Nenhum commit, push, merge, release, publicação PyPI ou deploy foi realizado nesta etapa. As integrações nativas continuam com as limitações científicas registradas na V4; não há nova alegação de convergência, causalidade ou validação empresarial.
