# Evidências públicas

Todos os dados são sintéticos. Arquivos de modelos nativos, ambientes, logs upstream e configurações pessoais ficam somente no armazenamento local, fora do Git e do sdist.

- `mcp-cycle.json`, `dashboard.html` e `report.md`: ciclo local ampliado com SDK oficial, descoberta de 15 ferramentas, execução das 12 ferramentas locais e persistência após reinício.
- `*-mcp.json`: cópias revisadas dos ciclos nativos da etapa anterior, com treino real, consulta, reconstrução do formato nativo e cenário em novo processo MCP. Não são mocks nem execução de CI dos frameworks opcionais.
- `*-extended.json` e `pymc-diagnostics.json`: diagnósticos estatísticos sintéticos; o baixo R² do Meridian e limitações de convergência dos smokes permanecem explícitos.
- `dependency-audit.json`: consulta ao PyPI dos seis locks Python, sem resolver/remediar automaticamente pacotes; descreve exclusões e achados. Não cobre advisories R.
- O progresso e os links de CI estão em `../../IMPLEMENTATION_PROGRESS.md`.

Os relatórios históricos em docs podem citar arquivos sob evidence/ que foram preservados somente na máquina original. Estes arquivos não são parte da distribuição pública. Não confundir evidência histórica, reexecução local e jobs observados no GitHub.
