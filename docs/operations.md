# Operação local 0.2

## Ambiente principal

Python 3.11+ e `pip install -e '.[dev]'` na venv. O SDK foi migrado para MCP 2.3: `MCPServer`, `Client` e campos Python `structured_content`/`is_error`. Confira também `ToolResponse.ok`; erros de esquema anteriores ao serviço são erros do protocolo. O wrapper `server.py` permanece.

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
