# Evidências públicas

Atualização V4.2 de 28/10/2026: [continuação e CI](../v42-followup.md) e
`v42-followup/` registram correções multiplataforma, teste real de contêiner,
wheel isolado e instalações uvx/pipx. As evidências anteriores abaixo são históricas.

Todos os dados são sintéticos. Arquivos de modelos nativos, ambientes, logs upstream e configurações pessoais ficam somente no armazenamento local, fora do Git e do sdist.

Segurança 0.3.1: `security031/` contém o ciclo atual, dashboard com hash CSP, relatório, CSV e auditoria. `security031-checks.json` agrega HTTP, recuperação, scanners e recargas nativas, com escopo explícito. A [auditoria de segurança](../../SECURITY_DEPLOY_AUDIT.md) é a referência para esta entrega somente GitHub, sem produção.

Evidências atuais 0.3: `scientific-final/` contém CSV, dashboard, relatório, auditoria e ciclo stdio de 16 ferramentas/13 locais; `scientific-meridian.json`, `scientific-pymc.json` e `scientific-robyn.json` são novos treinos nativos reais com recarga. `scientific-stress.json` contém 11 casos construídos; `scientific-ui.json` registra a paridade JS/Python; `scientific-http.json` confirma transporte/autorização. `scientific-checks.json` agrega verificações e `scientific-github-ci.json` confirma dez jobs, incluindo 105 testes em cada combinação OS/Python. Os arquivos listados abaixo são evidências históricas 0.2.

- `mcp-cycle.json`, `dashboard.html` e `report.md`: ciclo local ampliado com SDK oficial, descoberta de 15 ferramentas, execução das 12 ferramentas locais e persistência após reinício.
- `*-mcp.json`: cópias revisadas dos ciclos nativos da etapa anterior, com treino real, consulta, reconstrução do formato nativo e cenário em novo processo MCP. Não são mocks nem execução de CI dos frameworks opcionais.
- `*-extended.json` e `pymc-diagnostics.json`: diagnósticos estatísticos sintéticos; o baixo R² do Meridian e limitações de convergência dos smokes permanecem explícitos.
- `dependency-audit.json`: consulta ao PyPI dos seis locks Python, sem resolver/remediar automaticamente pacotes; descreve exclusões e achados. Não cobre advisories R.
- O progresso e os links de CI estão em `../../IMPLEMENTATION_PROGRESS.md`.

Os relatórios históricos em docs podem citar arquivos sob evidence/ que foram preservados somente na máquina original. Estes arquivos não são parte da distribuição pública. Não confundir evidência histórica, reexecução local e jobs observados no GitHub.
