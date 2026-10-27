# Operação local 0.2

## Ambiente principal

Python 3.11+ na venv. Para reproduzir o CI 0.3.1, instale `requirements/base-ci.txt` com `--require-hashes --only-binary=:all:` e depois o projeto com `--no-deps --no-build-isolation -e .`, conforme README. O lock universal inclui dev e scanners; os locks anteriores são snapshots históricos ou dos runtimes opcionais, não instalações concorrentes. O SDK usa MCP 2.3: `MCPServer`, `Client` e campos Python `structured_content`/`is_error`. Confira também `ToolResponse.ok`; erros de esquema anteriores ao serviço são erros do protocolo. O wrapper `server.py` permanece.

O lock principal registra Windows/Python 3.12; os locks em `requirements/` registram os outros ambientes. Para outra plataforma, resolva pelo pyproject e teste: pacotes Windows não são portáveis ao Linux. A matriz em `.github/workflows/ci.yml` prepara Windows/Linux/macOS e Python 3.11/3.12/3.13, sem publicação/deploy.

A revisão de publicação atualizou pytest para 9.0.3 por advisory conhecido e regenerou o lock Windows principal e 3.11; o lock Linux foi resolvido por uv preservando os demais pinos. Os resultados observados de CI e auditoria constam em `IMPLEMENTATION_PROGRESS.md` e `docs/validation`. Use `python examples/http_smoke.py --output-dir evidence/nova-verificacao-http` para repetir a conexão HTTP real sem sobrescrever resultados anteriores. O diretório de saída inclui dados/logs privados e é ignorado pelo Git.

## Motores separados

Meridian e PyMC-Marketing exigem versões incompatíveis de ArviZ. Nesta máquina existem venvs Python 3.12 em `var/envs/meridian`, `var/envs/pymc` e `var/envs/robyn`. O servidor invoca workers fixos, sem shell. Comandos usados após criar cada venv:

```powershell
.\var\envs\meridian\Scripts\python.exe -m pip install 'google-meridian[schema]==2.1.0'
.\var\envs\pymc\Scripts\python.exe -m pip install 'pymc-marketing==1.3.0' h5netcdf
.\var\envs\robyn\Scripts\python.exe -m pip install nevergrad 'numpy<2.4'
```

Meridian persiste Protobuf oficial; PyMC usa NetCDF/h5netcdf e solicita explicitamente `y_original_scale`. Robyn usa **R Robyn 3.12.1**, não o framework web Python homônimo.

R portátil 4.5.2 foi baixado de [Posit/r-builds](https://github.com/rstudio/r-builds), sem instalador/Registro/PATH, e extraído em uma pasta nova `var/runtime/r-portable`. [ZIP usado](https://cdn.posit.co/r/windows/R-4.5.2-windows.zip). É distribuição experimental/comunitária. Crie uma biblioteca privada e instale binários:

```powershell
$env:R_LIBS_USER = Join-Path $PWD 'var\runtime\r-library'
$env:RETICULATE_AUTOCONFIGURE = 'FALSE'
.\var\runtime\r-portable\R-4.5.2\bin\Rscript.exe --vanilla -e "install.packages(c('Robyn','jsonlite'), lib=Sys.getenv('R_LIBS_USER'), repos='https://cloud.r-project.org', type='binary', dependencies=NA)"
```

O bridge define `RETICULATE_PYTHON` para a venv Nevergrad e `R_LIBS_USER` para a biblioteca privada. Nunca instala pacotes durante uma chamada MCP. No Windows, o R usa um diretório privado automaticamente limpo na raiz temporária autorizada do SO, pois seu tempdir não aceita espaços. Artefatos finais ficam na raiz configurada.

Em outra instalação, defina caminhos absolutos em `MMM_MERIDIAN_PYTHON`, `MMM_PYMC_PYTHON`, `MMM_ROBYN_PYTHON` e `MMM_RSCRIPT`. `backend_status` confirma apenas presença do executável; não certifica bibliotecas ou convergência.

## Aceitação real dos motores

```powershell
.\.venv\Scripts\python.exe examples\backend_smoke.py --backend google_meridian --data-dir var\novo-meridian --output-dir evidence\novo-meridian
.\.venv\Scripts\python.exe examples\backend_smoke.py --backend pymc_marketing --data-dir var\novo-pymc --output-dir evidence\novo-pymc
.\.venv\Scripts\python.exe examples\backend_smoke.py --backend meta_robyn --data-dir var\novo-robyn --output-dir evidence\novo-robyn
```

Execute **sequencialmente**. O script usa stdio real para gerar, treinar, consultar, restaurar e calcular cenário após novo processo. `draws=50` é um smoke curto; no Robyn vira pelo menos 200 iterações/um trial. Volumes upstream de análise substantiva são maiores. Inspecione R-hat, ESS, divergências, sensibilidade e adequação ao problema.

`predict_backend` oferece cenários históricos suportados: Meridian mantém dimensões históricas, PyMC avalia holdout e Robyn calcula resposta por canal quando há multiplicadores. Não é o horizonte futuro do motor Ridge. Binários nativos são produzidos pelo próprio servidor, nunca fornecidos pelo cliente.

## HTTP autenticado

Stdio é padrão. HTTP é opt-in e escuta **somente 127.0.0.1**. `MMM_USERS_JSON` recebe usuários com `role` (`analyst`/`reader`) e `token_sha256` (64 hex). Cada usuário tem diretório próprio em `MMM_DATA_DIR/tenants/<usuario>`. Reader consulta/valida/simula, mas não cria dados, modelos ou relatórios. Compartilhamento não é automático.

Gere tokens fortes localmente; guarde somente hashes na configuração e não versione segredos. Envie `Authorization: Bearer ...`. Essa autenticação estática administrada pelo host não é um provedor OAuth corporativo. O cliente SDK pode fornecer o header pelo transporte.

```powershell
$env:MMM_TRANSPORT = 'streamable-http'
$env:MMM_PORT = '8769'
# Defina MMM_USERS_JSON com hashes e papéis adequados antes de iniciar.
.\.venv\Scripts\python.exe -m mmm_intelligence.server
```

`examples/http_smoke.py` inicia servidor em porta loopback livre, usa tokens efêmeros, verifica 401 sem token, separação entre usuários e bloqueio de escrita do reader, e encerra o processo.

## Recursos e diagnóstico

BLAS/OMP usam uma thread no servidor. Um semáforo permite um cálculo ativo por instância; outro recebe `BUSY`. Workers têm timeout de 900 s, configurável 10–3600. No Windows, Job Object aplica CPU hard cap (50%), memória total de 4096 MB e encerramento da árvore, incluindo R. Falha ao aplicar o controle falha a chamada. POSIX usa grupo de processos/timeout; não configura cgroup automaticamente.

Os controles não alteram plano de energia nem configurações globais. Não são sandbox contra código hostil ou quota distribuída entre instâncias. Não inicie vários motores pesados simultaneamente. Logs nativos privados de falha são limitados a 1 MB; podem conter tracebacks/caminhos upstream. Proteja-os por ACL e não publique logs empresariais.

## Auditoria 0.3 e artefatos grandes

`audit_model` também é permitido ao reader, com semáforo de cálculo, sem criar arquivos. O relatório completo fica no retorno estruturado; exporte-o pelo cliente. Repita stress com `python examples/scientific_stress.py --output-dir evidence/novo-stress`.

Os smokes nativos desta auditoria usaram `MMM_MAX_FILE_BYTES=52428800` explicitamente no host para acomodar serialização nativa. O padrão continua 10 MiB; não aumentar por argumentos de ferramenta. Declare target_type e contexto ao importar. Meridian recusa KPI não monetário/indefinido nesta interface; Robyn distingue receita/conversões. Priors efetivos e regras de holdout acompanham cada modelo novo. Artefatos 0.2 são evidência histórica; para avaliar as correções use os treinos 0.3 documentados.

HTTP usa tokens opacos estáticos, com `expires_at` e `disabled` opcionais desde 0.3.1; não implementa refresh OAuth. Não há chamadas a APIs de anúncios neste servidor; indisponibilidade ou autenticação de uma futura fonte externa não foi homologada por estes testes. Ausência de fonte real está registrada, não simulada como conexão empresarial bem-sucedida.

## Segurança 0.3.1

Perfil estrutural de usuário, com hash placeholder que deve ser substituído pelo operador:

~~~json
{"analista":{"role":"analyst","token_sha256":"<64 caracteres hex do SHA-256 do token>","expires_at":"2027-01-01T00:00:00Z","disabled":false}}
~~~

Não coloque o token original nesse JSON. Gere um token forte localmente e entregue-o ao cliente por canal seguro. Expiração exige timezone e é conferida em cada nova requisição. Para revogar, altere/remova o hash ou marque disabled e reinicie. Tokens antigos sem expires_at continuam sem vencimento automático, por compatibilidade; não confundir isso com sessão OAuth. Configuração inválida impede startup.

Limites por processo: `MMM_HTTP_REQUESTS_PER_MINUTE` (1–10000, padrão 120 por usuário), `MMM_HTTP_UNAUTH_PER_MINUTE` (1–1000, padrão 30 no bucket anônimo) e `MMM_HTTP_MAX_CONCURRENT` (1–32, padrão 4 por usuário). Respostas 429 incluem Retry-After. São controles locais, não quotas distribuídas. O semáforo de cálculo continua separado. Não há reload automático de configuração.

Workers não herdam credenciais arbitrárias do host. Apenas variáveis de SO, caminhos/certificados e MMM_RSCRIPT passam pela allowlist; limites de recursos são aplicados pelo processo pai. stdout/stderr é drenado e preserva no máximo 1.000.000 bytes finais, com marcador de truncamento. Isso não é isolamento de código hostil nem quota total de armazenamento.

Para repetir os checks: `python -m mypy src`, `python -m bandit -r src`, `python examples/check_secrets.py` e `python -m pip_audit --no-deps --disable-pip -r requirements/base-ci.txt`. O scanner de segredos reporta somente localização/regra, nunca o valor encontrado. `examples/http_smoke.py` também executa negativas de expiração/host/origin/body e limite, além de pequena amostra de latência em servidor descartável.

Backup local: pare a instância, copie a raiz de dados para um diretório novo protegido por ACL, exclua logs/jobs da cópia publicável e valide todos os envelopes/hashes. Restaure somente em outra raiz nova e compare uma consulta/simulação antes de trocar MMM_DATA_DIR. Não sobrescreva uma raiz existente nem trate Git como backup de dados privados. A entrega 0.3.1 não implanta serviço externo.

## CLI, retenção e distribuição V4

[Instalação](installation.md) cobre console doctor/config e wheel. Inventário MCP
verifica hashes e enumera apenas datasets/models/backend_models/reports/dashboards.
Logs, jobs, runtimes e backups não entram na soma. retention_plan usa mtime em dias,
que não substitui política jurídica de retenção, e lista dependentes sem apagar.

Para excluir um artefato revisado: pare o servidor, revise backup/dependentes e execute
`mmm-intelligence-mcp delete-artifact --data-dir RAIZ --kind reports --id ID --sha256 HASH`.
Exige raiz existente, ID permitido, hash exato e ausência de referências. Honra limites
MMM_MAX_FILE_BYTES do host; não faz exclusão recursiva. Uma exclusão não remove cópias,
logs ou backups. Não há quota global de disco nem coleta automática de lixo. O operador
local e ACL continuam sendo fronteira de confiança; não há defesa total contra outro
processo hostil com escrita simultânea na mesma raiz.

Workflows release-check e native-engines são manuais e somente leitura. Native-engines
prepara Windows/Python 3.12 para PyMC/Meridian, executa treino curto, recarga e projeção
quando suportada. Robyn ainda não tem job de provisionamento R. Nenhum novo workflow
foi executado remotamente nesta entrega. O teste do wheel usa venv descartável fora do
checkout; não confundir com certificação dos nove ambientes. O mínimo CI de 80% de
linhas parte de baseline medido de 82,35%, sem excluir workers difíceis do denominador.
Subprocessos não são instrumentados nessa cobertura; testes nativos são evidência separada.
