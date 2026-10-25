# Robyn: runtime R portátil e contrato de execução

Pesquisa em **24/10/2026**, somente leitura e documentação. Nenhum runtime foi instalado, nenhum instalador foi executado e nenhum treino ocorreu nesta pesquisa.

## Caminho viável no Windows

O projeto **rstudio/r-builds**, mantido no GitHub da organização Posit/RStudio, distribui R para Windows em ZIP portátil. Seu pipeline extrai o instalador CRAN e preserva o runtime; é uma distribuição **experimental e comunitária, sem suporte profissional da Posit**. O ZIP pode ser extraído em uma pasta do projeto, usando `Expand-Archive`, sem 7-Zip, admin, Registro, Docker ou WSL. O R básico é relocável, conforme a própria FAQ do R. Fontes: [r-builds README](https://github.com/rstudio/r-builds/blob/main/README.md), [Windows portable](https://github.com/rstudio/r-builds/blob/main/windows/README.md), [FAQ R Windows, seção 2.6](https://cran.r-project.org/bin/windows/base/rw-FAQ.html).

Verificação **HTTP HEAD real**, sem baixar o conteúdo:

| URL | HTTP | Content-Length | Last-Modified |
|---|---:|---:|---|
| `https://cdn.posit.co/r/windows/R-4.6.1-windows.zip` | 200 | 111.309.082 bytes | 29/06/2026 17:59:41 GMT |
| `https://cdn.posit.co/r/windows/R-4.5.2-windows.zip` | 200 | 108.621.778 bytes | 20/05/2026 21:52:48 GMT |
| `https://cdn.posit.co/r/windows/R-4.4.3-windows.zip` | 200 | 106.352.513 bytes | 20/05/2026 21:52:53 GMT |
| `https://github.com/dscharrer/innoextract/releases/download/1.9/innoextract-1.9-windows.zip` | 200 | 520.705 bytes | 07/12/2021 21:55:56 GMT |

O sandbox bloqueou os primeiros HEAD; a mesma consulta somente leitura, após revisão automática, retornou os quatro HTTP 200 acima. Isso confirma disponibilidade do arquivo, **não integridade do conteúdo, presença do executável nem funcionamento do runtime**. Calcular SHA-256 do download antes de extrair e registrar URL/versão/hash no relatório de execução; um hash calculado localmente é registro de integridade, não assinatura do fornecedor.

Proposta: usar o ZIP **R 4.6.1**, versão atual cuja documentação CRAN foi consultada, em `var/runtime/R-4.6.1`. Executar o `Rscript.exe` encontrado nessa árvore por caminho absoluto; não depender de alteração no PATH. Inspecionar o ZIP antes de extraí-lo para confirmar que todos os caminhos relativos ficam no destino e recusar destino já existente. A estrutura documentada inclui `bin/R.exe`; localizar `bin/Rscript.exe` ou `bin/x64/Rscript.exe` e verificar a versão real. Fontes: [r-builds Windows](https://github.com/rstudio/r-builds/blob/main/windows/README.md), [manual R 4.6.1](https://cran.r-project.org/doc/manuals/r-release/R-admin.html).

**Não executar integralmente `windows/build.ps1`:** ele tenta Chocolatey e possui fallback que executa o instalador real. `/CURRENTUSER` limita o escopo do instalador, mas não garante ausência de registros de desinstalação ou tarefas adicionais. A FAQ confirma que o instalador pode criar entradas HKCU. Para esta tarefa, usar o ZIP pronto ou somente extração com innoextract, sem fallback automático. Fontes: [script de build](https://github.com/rstudio/r-builds/blob/main/windows/build.ps1), [FAQ R, seção 2.16](https://cran.r-project.org/bin/windows/base/rw-FAQ.html).

## Dependências locais sem configuração global

R Robyn **3.12.1** é a versão estável publicada no CRAN; requer interpretador R >=4.0. Não confundir os dois versionamentos. Há binários Windows do pacote: [CRAN Robyn](https://cran.r-project.org/package=Robyn).

Para instalação futura, criar biblioteca privada `var/runtime/r-library` e chamar `install.packages("Robyn", lib=biblioteca_privada, repos="https://cloud.r-project.org", type="binary", dependencies=NA)`. `dependencies=NA` inclui dependências necessárias, sem solicitar todos os pacotes opcionais. `type="binary"` evita iniciar compilação inesperada; se faltar binário, registrar a ausência e resolver explicitamente. Após instalar, capturar `packageVersion("Robyn")` e `installed.packages()` para gerar lock factual. A instalação desse pacote não foi executada nesta pesquisa. O gerenciamento de bibliotecas é documentado no [manual R, capítulo 6](https://cran.r-project.org/doc/manuals/r-release/R-admin.html).

Variáveis **somente do processo filho**, propostas:

- `R_LIBS_USER`: biblioteca R privada já criada.
- `R_USER`, `TMPDIR`, `TMP`, `TEMP`: diretórios graváveis internos para dados de usuário e temporários desse worker.
- `RETICULATE_PYTHON`: caminho absoluto de um Python/venv dedicado com Nevergrad instalado.
- `RETICULATE_AUTOCONFIGURE=FALSE`: impede a configuração automática de dependências ao carregar pacotes.
- `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`: pedidos de limitação de threads numéricas; não substituem cotas do SO.

Invocar `Rscript --vanilla arquivo_worker.R` em subprocesso sem shell. Não usar `setx`, Registro nem perfil global. `RETICULATE_PYTHON` sobrepõe a descoberta automática e `RETICULATE_AUTOCONFIGURE` é documentada oficialmente: [reticulate/use_python](https://rstudio.github.io/reticulate/reference/use_python.html), [configure_environment](https://rstudio.github.io/reticulate/reference/configure_environment.html).

Desabilitar **execução** de Prophet é possível por `prophet_vars=NULL`, `prophet_country=NULL` e `dt_holidays=NULL`. Porém Prophet permanece em `Imports` e no `NAMESPACE` do Robyn; seu pacote e dependências ainda precisam estar instalados para carregar Robyn. Não editar o pacote removendo imports. Fontes: [inputs.R](https://github.com/facebookexperimental/Robyn/blob/main/R/R/inputs.R), [NAMESPACE](https://github.com/facebookexperimental/Robyn/blob/main/R/NAMESPACE).

## Contrato R mínimo para o dataset sintético atual

Exemplo de referência a implementar/testar no worker; **não executado**. `df` é o data.frame sintético validado, com 156 linhas semanais e as colunas já existentes. `private_json` é um arquivo temporário interno escolhido pelo servidor, nunca um caminho recebido do cliente.

```r
suppressPackageStartupMessages(library(Robyn))

media <- c("spend_search", "spend_social", "spend_video")
stopifnot(nrow(df) == 156L)
df$date <- as.Date(df$date)
stopifnot(!anyNA(df), !anyDuplicated(df$date))
stopifnot(all(diff(df$date) == 7))

# Controles determinísticos opcionais para evitar omitir baseline/estação
# quando a decomposição Prophet está desativada.
days <- as.numeric(df$date - min(df$date))
df$trend_years <- days / 365.25
df$sin_year <- sin(2 * pi * days / 365.25)
df$cos_year <- cos(2 * pi * days / 365.25)
controls <- c("price_index", "promotion", "trend_years", "sin_year", "cos_year")

hyps <- list(train_size = 0.6)
for (channel in media) {
  hyps[[paste0(channel, "_alphas")]] <- c(0.5, 3)
  hyps[[paste0(channel, "_gammas")]] <- c(0.1, 0.9)
  hyps[[paste0(channel, "_thetas")]] <- c(0, 0.8)
}

InputCollect <- robyn_inputs(
  dt_input = df,
  date_var = "date",
  dep_var = "revenue",
  dep_var_type = "revenue",
  paid_media_spends = media,
  paid_media_vars = media,
  paid_media_signs = rep("positive", length(media)),
  context_vars = controls,
  context_signs = rep("default", length(controls)),
  organic_vars = NULL,
  factor_vars = NULL,
  dt_holidays = NULL,
  prophet_vars = NULL,
  prophet_country = NULL,
  adstock = "geometric",
  hyperparameters = hyps,
  calibration_input = NULL,
  window_start = as.character(df$date[9]),
  window_end = as.character(tail(df$date, 1))
)

OutputModels <- robyn_run(
  InputCollect = InputCollect,
  trials = 1L,
  iterations = 200L,
  cores = 1L,
  ts_validation = TRUE,
  seed = 42L,
  nevergrad_algo = "TwoPointsDE",
  intercept_sign = "unconstrained",
  outputs = FALSE,
  quiet = TRUE
)

OutputCollect <- robyn_outputs(
  InputCollect = InputCollect,
  OutputModels = OutputModels,
  pareto_fronts = 1,
  min_candidates = 1,
  clusters = FALSE,
  select_model = NULL,
  plot_pareto = FALSE,
  csv_out = NULL,
  export = FALSE,
  quiet = TRUE
)

candidate <- OutputCollect$resultHypParam
stopifnot(nrow(candidate) > 0)
candidate <- candidate[is.finite(candidate$nrmse_val), , drop = FALSE]
stopifnot(nrow(candidate) > 0)
candidate <- candidate[order(candidate$nrmse_val, candidate$solID), , drop = FALSE]
selected_id <- as.character(candidate$solID[1])

predictions <- OutputCollect$xDecompVecCollect
predictions <- predictions[predictions$solID == selected_id, , drop = FALSE]
stopifnot(all(is.finite(predictions$depVarHat)))

exported <- robyn_write(
  InputCollect = InputCollect,
  OutputCollect = OutputCollect,
  select_model = selected_id,
  add_data = TRUE,
  export = FALSE,
  quiet = TRUE
)
jsonlite::write_json(exported, private_json, pretty = TRUE, digits = 10)
readback <- robyn_read(private_json, quiet = TRUE)
stopifnot(readback$ExportedModel$select_model == selected_id)
```

Os controles determinísticos e as faixas acima são escolhas exploratórias do projeto. O gerador sintético contém tendência e sazonalidade similares; isso favorece métricas e não demonstra adequação a negócio. O intercepto livre é compatível com mídia positiva; não equivale a liberar coeficientes de mídia negativos. Fontes de contrato: [inputs.R](https://github.com/facebookexperimental/Robyn/blob/main/R/R/inputs.R), [demo.R/hiperparâmetros](https://github.com/facebookexperimental/Robyn/blob/main/demo/demo.R), [model.R](https://github.com/facebookexperimental/Robyn/blob/main/R/R/model.R), [outputs.R](https://github.com/facebookexperimental/Robyn/blob/main/R/R/outputs.R).

`train_size=0.6` reserva aproximadamente 20% para validação e 20% finais para teste. As oito semanas iniciais estão disponíveis para adstock, mas fora da janela modelada. Capturar a divisão exata efetivamente usada; não apresentar automaticamente os mesmos índices do motor Ridge. O ranking acima usa **validação**, não erro do teste. `nrmse` é a função objetivo; `nrmse_val` aparece no resultado de `ts_validation`. As 200 iterações/1 trial são um smoke: o código recomenda 2.000/5 e emite warning, sem impedir essa execução menor. Fontes: [model.R](https://github.com/facebookexperimental/Robyn/blob/main/R/R/model.R), [checks.R](https://github.com/facebookexperimental/Robyn/blob/main/R/R/checks.R).

`xDecompVecCollect` contém `ds`, `dep_var`, `depVarHat` e `solID`; **não presumir `yhat` ou `y_pred`**. Para comparação, ordenar `ds`, selecionar `solID` e calcular MAE/WAPE/R² com os grupos temporais efetivos. `rsq_train` nativo é R² ajustado e não deve ser rotulado como R² comum. Fonte: [pareto.R](https://github.com/facebookexperimental/Robyn/blob/main/R/R/pareto.R), [schema.R](https://github.com/facebookexperimental/Robyn/blob/main/demo/schema.R).

## Reinício e cenários sem pickle

O JSON oficial inclui entrada e hiperparâmetros selecionados. `robyn_recreate(private_json, quiet=TRUE, cores=1L, clusters=FALSE, plot_pareto=FALSE, csv_out=NULL)` reconstrói entrada e modelo via execução com hiperparâmetros fixos; retorna lista com `InputCollect` e `OutputCollect`. Isso pode executar cálculo e não é simplesmente desserializar coeficientes. Não fornecer `export=FALSE` repetido em `...`, pois a função já o passa internamente. Fonte: [json.R](https://github.com/facebookexperimental/Robyn/blob/main/R/R/json.R).

O worker deve gravar JSON somente em temporário privado; o supervisor valida tamanho/hash/esquema e publica de forma exclusiva, preservando a proteção atual contra sobrescrita. Não entregar `private_json` a chamadas remotas nem ler RDS arbitrário. Registrar versão do R, Robyn, Python, Nevergrad, seleção, avisos e controles derivados.

Para cenários do mesmo período, o caminho nativo documentado é `robyn_response(InputCollect, OutputCollect, select_model=..., metric_name=..., metric_value=..., date_range=...)`. O retorno contém vetores `response_total` e `response_carryover`; não chamar isso automaticamente de previsão completa de receita futura. Saturação é Hill com `inflexion=max(adstocked_media)*gamma`; recalcular o máximo com cenário pode mudar a escala e invalidar comparação. Reutilizar a referência histórica ou delegar à API nativa e verificar igualdade no cenário sem alteração. Fontes: [response.R](https://github.com/facebookexperimental/Robyn/blob/main/R/R/response.R), [transformation.R](https://github.com/facebookexperimental/Robyn/blob/main/R/R/transformation.R).

## Evidências ainda necessárias

1. Download/extração do ZIP em pasta exclusiva e execução de `Rscript --version`.
2. Instalação binária local de Robyn e suas dependências; `library(Robyn)` sem autoconfiguração externa.
3. Nevergrad local reconhecido por reticulate usando exatamente o Python configurado.
4. Execução do fit real com timeout e apenas dados sintéticos.
5. Conferência de coeficientes de mídia, datas, predições, erro de holdout e logs.
6. Serialização JSON, reinício em novo processo e comparação numérica das previsões reconstruídas.
7. Cenário sem alteração reproduzindo o resultado base; mudança de mídia passando pela API Robyn efetiva.

Até essas verificações, o status correto é runtime/integração pesquisados, não homologados.
