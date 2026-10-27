# MMM Intelligence MCP — 0.4.0

Servidor independente de Marketing Mix Modeling com **SDK oficial MCP 2.3**, execução local e resultados exploratórios. Há **26 ferramentas**, motor Ridge e adaptadores nativos para **Google Meridian, PyMC-Marketing e Meta Robyn**, importação CSV/JSON, qualidade de dados, comparação padronizada, projeção futura Ridge/PyMC, otimização local e dashboard.

Nenhuma ferramenta altera campanhas ou orçamentos reais. Dados sintéticos são o padrão. Integração funcional é diferente de convergência estatística e identificação causal.

Licença **Apache-2.0**, autorizada pelo proprietário; consulte [LICENSE](LICENSE) e [NOTICE](NOTICE). A versão 0.4.0 está preparada na branch local `feat/v4-intelligence`; a publicação anterior no [GitHub](https://github.com/matheusfrote/mmm-intelligence-mcp) é 0.3.1. A matriz CI preserva Windows/Linux/macOS e Python 3.11/3.12/3.13; a V4 foi executada localmente em Windows/Python 3.12.14. O novo CI remoto ainda não foi executado. [Entrega V4 e evidências](docs/v4-delivery.md).

## Começar

**Dashboard local sem login:** depois de instalar, execute `mmm-intelligence-mcp dashboard` e abra `http://127.0.0.1:8769/app`. Não é necessário configurar ou informar token para o workspace local. O endpoint MCP separado continua protegido. [Guia do dashboard V4.2 e testes](docs/dashboard.md).

Python 3.11+ para o servidor base; PyMC-Marketing 1.3 exige Python 3.12 em seu ambiente separado.

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements/base-ci.txt
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python.exe -m pip check
$env:MMM_DATA_DIR = Join-Path $PWD 'var'
.\.venv\Scripts\python.exe -m mmm_intelligence.server
~~~

Stdio aguarda um cliente MCP, sem abrir URL. Alternativas: python server.py ou o entrypoint mmm-intelligence-mcp. Stdout é exclusivo do protocolo. Adapte os caminhos absolutos da [configuração de exemplo](examples/mcp-config.example.json) ao seu cliente. No Windows, use `.venv/Scripts/python.exe` como command. Nenhum cliente global é alterado pelo servidor.

`mmm-intelligence-mcp doctor` verifica a instalação; `mmm-intelligence-mcp config --data-dir C:\mmm-data` imprime configuração stdio. [Instalação por checkout, wheel e ambientes isolados](docs/installation.md). O pacote não foi publicado no PyPI e não instala runtimes opcionais automaticamente.

## Demonstração completa

~~~powershell
.\.venv\Scripts\python.exe examples\mcp_workflow.py --extended --data-dir var\minha-demo --output-dir evidence\minha-demo
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests examples server.py
~~~

Use pasta de evidências nova em cada execução. O exemplo verifica descoberta, chamadas estruturadas, erros e persistência após reinício. Exporta HTML interativo, Markdown e CSV completos.

Artefatos V4: [dashboard](docs/validation/v4/dashboard.html), [relatório](docs/validation/v4/report.md), [CSV sintético](docs/validation/v4/demo.csv) e [índice de evidências](docs/validation/v4/README.md). O dashboard funciona localmente sem CDNs nem requisições externas. Evidências anteriores permanecem históricas.

## Ferramentas

Todas recebem um objeto request e retornam ToolResponse. Confira ok; o validador também exige data.valid=true. O cliente Python SDK 2 usa structured_content e is_error.

| Ferramenta | Função |
|---|---|
| generate_demo_dataset | Cria dados sintéticos reproduzíveis, diários/semanais |
| validate_dataset | Examina colunas, valores, datas, regularidade e split |
| train_mmm | Ridge, adstock, Hill, mídia positiva, holdout e bootstrap opcional |
| get_model | Consulta parâmetros, diagnósticos, previsões e estado |
| audit_model | Reconcilia componentes, backtests, sensibilidade e motivos de abstenção |
| simulate_budget | Cenário futuro com horizonte, controles e carryover |
| import_dataset | Importa linhas inline com procedência e autorização |
| optimize_budget | Otimiza total fixo e mínimos/máximos por canal |
| tune_mmm | Seleciona retenção/K em validação anterior ao teste externo |
| calibrate_experiment | Repondera draws condicionais com lift e erro padrão declarados |
| render_dashboard | Gera HTML interativo independente, sem sobrescrita |
| generate_report | Gera Markdown reconciliado com os resultados |
| backend_status | Lista capacidades e presença dos runtimes opcionais |
| train_backend | Treina o motor externo verdadeiro em ambiente isolado |
| get_backend_model | Consulta resultados do motor externo |
| predict_backend | Recarrega o formato nativo e calcula cenário histórico suportado |
| import_csv | Importa CSV inline com mapeamento, fuso, decimais e agregações explícitas |
| data_quality | Examina lacunas, variabilidade, extremos, colinearidade e mudanças de nível |
| get_analysis | Retorna contrato canônico com métricas, linhagem, intervalos e diagnósticos |
| compare_models | Recalcula métricas nas mesmas datas e impede comparações incompatíveis |
| model_capabilities | Explicita operações disponíveis por motor |
| forecast_model | Projeta plano por período com controles explícitos em Ridge/PyMC |
| export_analysis | Exporta análise em JSON, CSV ou Markdown no retorno |
| storage_inventory | Lista artefatos verificados, tamanhos, hashes e referências |
| retention_plan | Propõe candidatos por idade sem excluir arquivos |
| connector_status | Declara estado dos contratos de fontes; nenhuma API conectada |

Exemplo de treino local, depois de gerar o dataset:

~~~json
{"request":{"dataset_id":"demo-exemplo","model_id":"modelo-exemplo","bootstrap_samples":100}}
~~~

Simulação:

~~~json
{"request":{"model_id":"modelo-exemplo","horizon":13,"total_budget":52000,"allocation":{"spend_search":0.5,"spend_social":0.3,"spend_video":0.2}}}
~~~

O orçamento é o **total de todo o horizonte**, na unidade do dataset, dividido igualmente entre períodos. A referência usa a média dos últimos até 13 gastos por período; o retorno mostra ambos os totais. Os valores sintéticos não são reais nem valores de uma conta.

Para otimizar, use model_id, horizon, total_budget e dicionários opcionais lower/upper com limites totais por canal. `optimal_spend` é candidato do modelo; `recommended_spend` permanece null e `decision_support` explica os limites. A comparação usa referência com o mesmo total. Para auditar, envie `{"request":{"model_id":"modelo-exemplo"}}` a `audit_model`. Para treinar motor externo:

~~~json
{"request":{"dataset_id":"demo-exemplo","backend":"google_meridian","draws":50,"tune":50,"chains":2}}
~~~

Use pymc_marketing ou meta_robyn nos outros adaptadores. Robyn requer `test_fraction=0.2`: sua divisão nativa é 60/20/20 com arredondamento próprio; valores diferentes são rejeitados. Esses volumes curtos são teste de execução, **não ajuste certificado**. predict_backend recebe model_id e media_multiplier, por exemplo {"spend_search":1.1}, para cenário histórico. Para datas futuras, `forecast_model` aceita Ridge/PyMC, plano de mídia e todos os controles por período. Meridian/Robyn retornam indisponibilidade explícita nessa operação. [Contratos e comparação](docs/comparison.md).

## Arquitetura e limites

Servidor, contratos, validação, modelagem, análise, simulação, otimização, persistência, renderização e integrações são módulos separados em src/mmm_intelligence. Motores externos usam workers independentes e serialização Protobuf, NetCDF ou JSON oficial; não há fallback Ridge com outro rótulo nem uso de pickle/RDS.

Bootstrap produz intervalos da **média condicional** com formas/inputs fixos; não é intervalo preditivo completo. Calibração é reponderação aproximada, sem demonstrar randomização ou transporte. Bom R² não certifica atribuição por canal. Diagnósticos e alertas permanecem visíveis, inclusive quando a convergência é ruim.

O estudo V4 de 60 ajustes encontrou subcobertura e falha dos intervalos percentis para efeitos nulos na fronteira. Não use seus limites para testar existência de efeito. Os smokes bayesianos mantêm diagnósticos inadequados; não foram transformados em modelos certificados. [Resultados científicos](docs/v4-delivery.md).

Importações declaram `target_type` como revenue, non_revenue ou unspecified, além de `data_context`. Meridian exige receita declarada; Robyn distingue receita/conversões e recusa tipo indefinido. Os treinos nativos curtos publicados comprovam execução, mas os diagnósticos MCMC não aprovam uso inferencial. ROI/mROI causal não são inferidos de contribuição/gasto. Consulte a [auditoria 0.3](MMM_AUDIT_REPORT.md), [matriz científica](MMM_VALIDATION_MATRIX.md), [qualidade dos dados](MMM_DATA_QUALITY.md) e [resultados executados](MMM_VALIDATION_RESULTS.md).

Arquivos são acessados por IDs. Dados reais exigem MMM_ALLOW_REAL_DATA=true no host e referência de autorização explícita. Nenhum dado real foi usado nesta entrega. HTTP é opcional, autenticado, com papéis e diretório por usuário, escutando somente 127.0.0.1.

## Configuração

| Variável | Padrão / função |
|---|---|
| MMM_DATA_DIR | ./var, raiz autorizada |
| MMM_ALLOW_REAL_DATA | false |
| MMM_MAX_ROWS / MMM_MAX_FILE_BYTES | 10000 / 10485760 |
| MMM_LOG_LEVEL | INFO |
| MMM_TRANSPORT / MMM_PORT | stdio / 8769; HTTP opcional |
| MMM_USERS_JSON | Usuários HTTP: token_sha256 e role analyst/reader |
| MMM_HTTP_REQUESTS_PER_MINUTE | 120 por usuário, por processo |
| MMM_HTTP_UNAUTH_PER_MINUTE | 30 negativas anônimas por processo |
| MMM_HTTP_MAX_CONCURRENT | 4 requisições simultâneas por usuário |
| MMM_MERIDIAN_PYTHON / MMM_PYMC_PYTHON / MMM_ROBYN_PYTHON | Python de cada runtime opcional |
| MMM_RSCRIPT | Executável Rscript portátil |
| MMM_BACKEND_TIMEOUT_SECONDS | 900 |
| MMM_WORKER_CPU_PERCENT / MMM_WORKER_MEMORY_MB | 50 / 4096, Job Object Windows |

.env.example é referência; .env não é carregado automaticamente. Não versionar segredos. Eventos ficam em var/logs; logs nativos privados podem conter tracebacks upstream. Limites de recursos afetam somente processos deste projeto, sem alterar ajustes globais do host.

## Documentação e evidências

[Operação e instalação](docs/operations.md) · [Ferramentas](docs/tools.md) · [Método](docs/methodology.md) · [Segurança](docs/security.md) · [Arquitetura](docs/architecture.md) · [Relatório da extensão](docs/extension-report.md).

A [auditoria de segurança 0.3.1](SECURITY_DEPLOY_AUDIT.md) documenta correções, testes negativos e limites. HTTP aceita expiração/bloqueio opcionais de token, rejeita Authorization duplicado e limita frequência/concorrência. Workers recebem somente variáveis de ambiente permitidas e têm log limitado. O CI usa lock com hashes, actions por SHA, Ruff, mypy básico, Bandit e scanner de padrões no histórico. Conforme orientação do usuário, a entrega é somente GitHub, sem deploy de serviço.

O [progresso de implementação](IMPLEMENTATION_PROGRESS.md) registra auditoria, correções, testes e estado verificável da publicação. Os [relatórios históricos](docs/delivery-report.md) podem referenciar evidências privadas locais excluídas da distribuição. A pasta `docs/validation` contém somente evidências sintéticas revisadas para publicação. Ambientes, modelos persistidos e logs privados não são versionados. Publicação do código no GitHub não inicia serviço nem publica pacote no PyPI.

Fontes: [SDK MCP](https://py.sdk.modelcontextprotocol.io/), [Meridian](https://developers.google.com/meridian), [PyMC-Marketing](https://www.pymc-marketing.io/), [Meta Robyn](https://facebookexperimental.github.io/Robyn/). Contratos e versões pesquisados estão em [engine-research.md](docs/engine-research.md).
