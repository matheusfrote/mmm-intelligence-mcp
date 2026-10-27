# Evidências V4 locais

Todos os datasets/resultados são sintéticos. Nenhum dado de conta, segredo, ambiente
ou binário nativo privado foi copiado. Registros antigos em outras pastas são históricos.

| Arquivo | Conteúdo |
|---|---|
| checks.json | Testes, cobertura, versões, alcance e estado remoto |
| mcp-cycle.json | Descoberta, 23 chamadas locais, negativas e reinício reais |
| demo.csv / dashboard.html / report.md / audit.json | Artefatos completos da demonstração |
| http.json | Servidor loopback real, autenticação, isolamento e limites |
| native-pymc.json / native-meridian.json / native-robyn.json | Recarga real de modelos existentes; PyMC futuro e novo processo |
| comparison.json | Quatro motores via MCP, recusa de janela exata e 30 datas comuns |
| recovery.json | Resumo de 60 ajustes controlados; sem certificação de cobertura |
| stress.json | Onze casos sintéticos e abstenção |
| ui.json | Inspeção Chrome real e comparação numérica com Python |
| dependency-audit.json | Quatro locks Python consultados, contagens e achados |
| licenses.json | Metadados de dependências diretas/frameworks, não auditoria jurídica transitiva |
| secrets.json | Scanner de padrões/worktree/histórico, sem valores de segredos |
| wheel-install.json | Wheel instalado em venv nova fora do checkout e ciclo MCP |
| changed-files.txt | Inventário do diff e arquivos novos desta entrega |

Repetição: criar novos diretórios de saída. `examples/mcp_workflow.py --extended`,
`http_smoke.py`, `scientific_stress.py` e `recovery_study.py` aceitam diretórios/arquivos
explicitamente fornecidos. `native_v4_check.py` requer raiz/ID de modelo nativo sintético
existente; `compare_native_models.py` recebe --model BACKEND ROOT ID repetido e usa
store temporário. `verify_wheel.py --wheel-dir dist/VERSAO --receipt ARQUIVO` instala
dependências fixadas por hash e executa fora do checkout. Runtimes opcionais permanecem
isolados. Comandos completos e limitações em [entrega](../../v4-delivery.md).

Wheel/sdist e logs completos permanecem localmente em dist/evidence/var, ignorados
pelo Git. O recibo não é publicação em PyPI nem execução de CI remoto.
