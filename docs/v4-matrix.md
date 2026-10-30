# V4 — inventário e execução

Baseline de 26/10/2026: commit `015eaeff6e6606bdaac70ff66c3ea4fe193660b1`, árvore limpa,
main local/remota iguais. Branch de trabalho: `feat/v4-intelligence`.
131 testes passaram em 29,47 s no Windows/Python 3.12.14, cobertura de linhas 82,35%
(1297/1575; `var/v4-baseline-coverage.json`). Um RuntimeWarning SciPy preexistente.
GitHub MCP consultou metadados; API pública confirmou main sem proteção, zero tags/releases;
PyPI retornou 404 para o nome. Essas consultas não alteraram configurações externas.

| Componente | Implementação atual | Evidência | Deficiência | Severidade | Prioridade | Correção | Teste de aceite | Status inicial |
|---|---|---|---|---|---|---|---|---|
| Licença | Não declarada | git ls-files/pyproject | Sem concessão explícita | Alta | P0 | Proposta Apache-2.0; decisão do proprietário | LICENSE/metadata coerentes | Ausente após verificação |
| Release | Sem tags/releases | API pública | Sem versão oficial distribuída | Moderada | P0 | Pipeline manual de preparação | Wheel instalado | Bloqueado por autorização de publicação |
| PyPI | Nome retorna 404 | Consulta pública | Sem pacote no índice | Moderada | P0 | Preparar metadados/build | Instalação limpa | Bloqueado por autorização/autenticação |
| Instalação | pip local, locks | README/CI | Sem CLI doctor/config | Moderada | P0 | CLI independente de MCP | subprocessos reais | Implementado parcialmente |
| Conectores | Ausentes | Todos os módulos | Sem APIs autenticadas | Alta | P0 | Contrato de fonte e reconciliação | Respostas controladas; real exige conta | Ausente após verificação |
| CSV | Somente exemplo/export | schemas/service | Sem importador MCP | Alta | P0 | CSV inline e transformações explícitas | Negativas + stdio | Ausente após verificação |
| Negócio real | Apenas sintéticos | Proveniência/evidências | Sem identificação causal empresarial | Alta | P0 | Protocolo de validação real | Dados/experimento autorizados | Bloqueado por dependência externa |
| Futuro nativo | Cenários históricos | worker.py/R | Sem horizonte futuro | Alta | P1 | PyMC futuro; capacidades explícitas | Worker nativo + carryover | Implementado parcialmente |
| Otimização | Ridge com restrições | optimization/tests | Nativos não expostos | Moderada | P1 | Contrato de capacidades, sem fallback | Inviáveis/soma/limites | Implementado parcialmente |
| CI nativo | Fora do CI | ci.yml | Sem jobs opcionais | Moderada | P1 | Workflow manual separado | Execução nativa identificada | Ausente após verificação |
| Dashboard | HTML local Ridge | rendering/UI histórico | Poucos painéis/exportações | Moderada | P1 | Qualidade/resíduos/curvas/export | Paridade Python/JS e navegador | Implementado parcialmente |
| Fluxo multietapas | Ferramentas separadas | server.py | Sem aplicação de treinamento UI | Moderada | P1 | Navegação analítica local | Navegação e conteúdo real | Implementado parcialmente |
| Geografia | Nacional | contratos/workers | Sem hierarquias/geo API | Moderada | P2 | Registrar escopo; evitar agregação implícita | Requer contrato/experimentos próprios | Ausente após verificação |
| Produção | Loopback | HTTP/tests | Sem serviço público | Informativa | P2 | Arquitetura futura | Destino/identidade/infra necessários | Não aplicável ao escopo autorizado |
| Filas | Síncrono/semáforo | service.py | Sem fila durável | Moderada | P2 | Interface e projeto operacional | Infra necessária | Ausente após verificação |
| Retenção | Imutabilidade/limites por arquivo | storage.py | Sem inventário/expurgo | Moderada | P1 | Inventário e plano de retenção seguro | Hashes/linhagem/sem exclusão implícita | Implementado parcialmente |
| Comunidade | README técnico | git ls-files | Guias/templates ausentes | Moderada | P0 | Governança e contribuição | Conteúdo/distribuição | Ausente após verificação |
| Proteção main | false | GitHub API branches | Sem regras obrigatórias | Alta | P0 | Proposta revisável | Aplicação externa autorizada | Bloqueado por autorização |
| Comparação | Tabelas históricas | relatórios | Sem mesmas datas/KPI verificados | Alta | P1 | Contrato canônico e comparação | Incompatibilidade rejeitada | Ausente após verificação |
| Fluxo unificado | 16 ferramentas | suite/servidor | Sem capacidades por operação | Moderada | P1 | Consulta/forecast/export canônicos | E2E real | Implementado parcialmente |

## Matriz operacional

| ID | Fase | Tarefa | Prioridade | Dependências | Arquivos | Testes | Resultado | Evidência | Estado |
|---|---|---|---|---|---|---|---|---|---|
| A | A | Baseline e inventário | P0 | Nenhuma | Este documento | pytest/cov | 131/0; 82,35% | coverage local, API GitHub | Concluído e validado |
| B | B | Governança/CLI/distribuição | P0 | A; licença autorizada | docs, CLI, workflows | CLI/build/instalação | Apache aplicada; pacote local | validation/v4 | Implementado com validação parcial |
| C | C | Diagnósticos/recuperação/abstenção | P0 | A | diagnostics/science/tests | 60 ajustes + 11 stress | Limites/boundary identificados; abstenção | recovery.json, stress.json | Implementado com validação parcial |
| D | D | CSV/qualidade/proveniência/fontes | P0 | B/C | ingestion/quality/connectors | Dados controlados + MCP | CSV/qualidade operacionais; APIs ausentes | tests/test_ingestion.py | Implementado com validação parcial |
| E | E | Contratos/comparação | P1 | C/D | canonical | Quatro motores, 30 datas | Recusa exata e interseção explícita | comparison.json | Concluído e validado |
| F | F | Futuro condicional | P1 | E/runtimes | forecasting/worker | PyMC nativo + Ridge | PyMC recarga/reinício; Meridian/Robyn sem futuro | native-pymc.json | Implementado com validação parcial |
| G | G | Painéis/exportação | P1 | E/F | rendering | Python/JS/Chrome | Painel Ridge, CSV/JSON, CSP e navegação | ui.json | Implementado com validação parcial |
| H | H | Ciclo de vida/operação | P1 | D/E | lifecycle/docs | Isolamento/hash/referências/CLI | Inventário/plano/exclusão unitária | tests/test_lifecycle.py, http.json | Implementado com validação parcial |
| I | I | Verificação final | P0 | B-H | reports/tests/CI | Suite/lint/tipos/build/MCP | 183/0; 81,57% linhas; sem achados nos locks Python | validation/v4 | Implementado com validação parcial |

Licença Apache-2.0 concedida após autorização expressa. Sem release, PyPI, alteração de regras GitHub ou deploy automáticos.
Strix permanece fora do escopo, conforme decisão anterior. Não há dados reais autorizados.

## Situação atual dos vinte itens do diagnóstico

| Item | Estado após V4 |
|---|---|
| Licença | Implementado e validado: Apache-2.0, NOTICE e metadados |
| Release / PyPI | Preparação local funcional; publicação bloqueada por autorização e conta PyPI |
| Instalação | CLI, wheel e instruções prontas; pipx/uvx sem execução independente |
| Conectores | Contratos/reconciliação offline; adapters ausentes após verificação |
| CSV | Implementado e validado com transformações explícitas |
| Negócio real | Bloqueado por dados/autorização/experimento externos |
| Futuro nativo | PyMC implementado/testado; Meridian/Robyn pendentes |
| Otimização | Ridge funcional; nativos sem implementação verificada |
| CI nativo | Workflow manual PyMC/Meridian preparado, sem execução remota; Robyn pendente |
| Dashboard | Painéis Ridge/exportação validados em navegador |
| Aplicação multietapas | Navegação analítica pronta; treino/comparação UI ausentes |
| Geografia | Ausente; API nacional preservada |
| Produção | Não aplicável ao escopo autorizado: GitHub somente |
| Filas | Arquitetura documentada; runtime durável ausente |
| Retenção | Inventário/plano e exclusão CLI validados; sem limpeza automática/quotas totais |
| Comunidade | Documentação/templates preparados |
| Proteção main | Proposta pronta; aplicação externa exige autorização |
| Comparação | Quatro modelos reais persistidos comparados em 30 datas sintéticas comuns |
| Fluxo unificado | 26 ferramentas, capacidades explícitas e limites por backend |

Diff associado: `git diff 015eaeff6e6606bdaac70ff66c3ea4fe193660b1` mais os arquivos
novos enumerados em validation/v4/changed-files.txt. Nenhum commit/push V4 realizado.
