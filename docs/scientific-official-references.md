# Auditoria científica: fontes oficiais e contratos nativos

Consulta e inspeção em **24/10/2026, America/Sao_Paulo**. Pesquisa somente leitura, sem amostragem MCMC nem ajuste Robyn. Este documento registra o estado encontrado no início desta auditoria; correções posteriores devem ser verificadas nos testes e no relatório científico principal. Versões confirmadas pelo metadata local: Google Meridian **2.1.0**, PyMC-Marketing **1.3.0**, Robyn R **3.12.1**, interpretador R **4.5.2**. Robyn foi compilado com R 4.5.3 e emite aviso no interpretador local.

## Fundamentos distintos

| Motor | Modelo efetivamente configurado no adaptador auditado | Incerteza e interpretação |
|---|---|---|
| Local | Ridge com coeficientes de mídia não negativos; adstock geométrico normalizado e Hill com expoente 1; hiperparâmetros fixos ou busca temporal separada | Bootstrap condicional da especificação; não é posterior bayesiana nem identificação causal automática. |
| Meridian | Modelo bayesiano nacional, adstock geométrico máximo 8, Hill, intercepto temporal por quatro knots; sem efeitos hierárquicos entre geos nesta entrada nacional | `expected_outcome` fornece amostras da média condicional; seus quantis não incluem automaticamente ruído observacional. |
| PyMC-Marketing | MMM bayesiano; `GeometricAdstock(l_max=8)`, saturação logística, um harmônico anual e controles declarados | O adaptador amostra `y_original_scale`: previsão posterior do observado, incluindo likelihood. Seus intervalos diferem dos intervalos de média Meridian. |
| Robyn | Regressão Ridge com sinais de mídia positivos, adstock geométrico e Hill; Nevergrad seleciona hiperparâmetros em objetivos múltiplos | `depVarHat` é previsão pontual. A busca reduzida e uma tentativa não constituem amostragem posterior nem convergência MCMC. |

As APIs e funções matemáticas são próprias de cada pacote; não se deve chamar os quatro modelos de implementações estatisticamente equivalentes. Fontes: [ModelSpec Meridian 2.1.0](https://github.com/google/meridian/blob/v2.1.0/meridian/model/spec.py), [MMM PyMC-Marketing 1.3.0](https://github.com/pymc-labs/pymc-marketing/blob/v1.3.0/pymc_marketing/mmm/mmm.py), [recursos Robyn](https://facebookexperimental.github.io/Robyn/docs/features/).

## Mídia, gasto e exposição

O worker Meridian duplica cada gasto como `exposure_*`; Robyn recebe as mesmas colunas em `paid_media_vars` e `paid_media_spends`; PyMC modela diretamente os valores declarados como canais. Trata-se de uma hipótese de proxy, não de impressões medidas. A documentação Meta permite fallback de gasto quando exposição não existe e recomenda investigar a relação gasto/exposição. No Meridian, gasto e exposição têm campos separados; documentar a duplicação é essencial. Nenhuma conversão de gasto em exposição física foi validada neste projeto. Fontes: [entradas Robyn](https://facebookexperimental.github.io/Robyn/docs/features/#paid-media-variables), [loader Meridian 2.1.0](https://github.com/google/meridian/blob/v2.1.0/meridian/data/load.py).

## Achado SREF-01: holdout Meridian não isola a normalização do target

**Confirmado por execução sem sampling.** O adaptador entrega todos os KPIs ao loader e especifica a cauda como holdout. A biblioteca mascara corretamente essa cauda na likelihood: `posterior_sampler._pin_dist` substitui o target mascarado por zero e o termo correspondente da distribuição tem densidade constante. Porém `ModelContext.kpi_transformer` recebe `self.kpi` completo; `KpiTransformer` calcula média/desvio de todos os KPIs antes dessa máscara. Alterar apenas o target futuro altera os valores escalados de treinamento.

Reprodução executada: 52 segundas-feiras desde 2020-01-06; target `100 + arange(52)`; gasto `10 + sin(arange(52))`; corte 41; max_lag=8, knots=4; 11 datas em `HoldoutSpec(DateRange(data[41], None))`. Duas construções de `Meridian` com target holdout original versus multiplicado por 100, sem `sample_prior` nem `sample_posterior`:

| Quantidade | Holdout original | Somente target holdout × 100 |
|---|---:|---:|
| Média interna target | 125.5 | 3183.0769230769233 |
| Desvio interno target | 15.008331019803634 | 5915.418652998001 |
| Primeiro target de treino escalado | -1.6990563418645626 | -0.5211933599178793 |
| Média prior ROI | 1.8312522088857732 | 1.8312522088857732 |

Inspecionar `fitted.kpi_transformer.population_scaled_mean`, `.population_scaled_stdev`, `fitted.kpi_scaled[0,0]` e `fitted.prior_broadcast.roi_m.mean()` reproduz os valores. Isso demonstra dependência do pré-processamento no target reservado; não mede o tamanho do efeito sobre a posterior, pois nenhum sampling foi executado. Fontes do código exato: [context.py, tag 2.1.0](https://github.com/google/meridian/blob/v2.1.0/meridian/model/context.py), [transformers.py](https://github.com/google/meridian/blob/v2.1.0/meridian/model/transformers.py), [posterior_sampler.py](https://github.com/google/meridian/blob/v2.1.0/meridian/model/posterior_sampler.py).

**Correção mínima proposta, a ser testada:** manter observado integral separado para métricas; na cópia exclusiva destinada ao loader preencher target holdout com média calculada somente no prefixo de treinamento; manter `HoldoutSpec` intacto. Assim mudar observado futuro não altera scaler nem modelo de treinamento. A escala ainda é calculada pela biblioteca sobre prefixo mais placeholders: não alegar equivalência com normalização ajustada exclusivamente no prefixo, nem alterar biblioteca instalada. Persistir máscara, política e valor do placeholder. Testar invariância das transformações e dos priors ao perturbar somente target holdout.

**Prior e nuance:** `prior_broadcast` recebe soma de KPI completo, mas o caminho que deriva ROI dessa soma é ativado para KPI não monetário sem `revenue_per_kpi`, com defaults apropriados. O adaptador atual usa `kpi_type='revenue'`; a reprodução confirma ROI prior igual. Não atribuir a este adaptador atual uma alteração do ROI prior por target futuro que não foi observada. Fonte: [prior_distribution.py 2.1.0](https://github.com/google/meridian/blob/v2.1.0/meridian/model/prior_distribution.py).

## Achado SREF-02: a cauda Robyn não é sempre `ceiling(n * 0.2)`

**Confirmado no código instalado Robyn 3.12.1**, usando `deparse(Robyn:::robyn_mmm)` sem fit. O split real é sequencial e usa, em R:

```r
train_size <- 0.6
val_size <- (1 - train_size) / 2
train_end <- floor(quantile(seq(n), train_size))
val_end <- train_end + floor(val_size * n)
test_indices <- (val_end + 1):n
```

O adaptador auditado usa `tail(predictions, ceiling(nrow(predictions)*0.2))`. Com janela de 94 linhas, teste nativo tem 20 e adapter somente 19; com 91 linhas, teste nativo tem 18 mas adapter 19, incluindo uma observação da validação. O erro depende também do ponto flutuante: preservar a expressão nativa `(1-train_size)/2`, não substituí-la por literal decimal. A janela começa após o warmup informado, de modo que `n` deve ser o tamanho efetivo da janela, não o dataset bruto. Corrigir pela máscara/datas nativas persistidas, verificar exatamente os índices e reportar treinamento, validação e teste separadamente. Seleção por `nrmse_val` é diferente de avaliar a cauda final; não selecionar candidato pela métrica final de teste. Fontes: [model.R oficial](https://github.com/facebookexperimental/Robyn/blob/main/R/R/model.R), [time series validation](https://facebookexperimental.github.io/Robyn/docs/features/#time-series-validation). O upstream `main` foi consultado, mas a confirmação de contrato veio do pacote instalado 3.12.1.

## Priors explícitos versus defaults

O código auditado **não fornece priors customizados nem faz sensibilidade de priors**. `sample_prior` Meridian produz draws de defaults; não demonstra sua adequação empresarial. Em 2.1.0 ROI monetário default é LogNormal(loc=0.2, scale=0.9). No PyMC 1.3.0 local: alpha adstock Beta(1,3), lambda logístico Gamma(alpha=3,beta=1), beta de saturação HalfNormal(sigma=2), controles Normal(0,2), Fourier Laplace(0,1). A classe atual aplica dimensões por canal via `with_default_prior_dims`; não concluir pooling incorreto apenas a partir do construtor sem `dims`. Estes valores dependem da versão; persistir a configuração efetiva e escala, e testar previsões a priori e sensibilidade antes de decisões. Fontes: [defaults Meridian](https://github.com/google/meridian/blob/v2.1.0/meridian/model/prior_distribution.py), [adstock PyMC](https://github.com/pymc-labs/pymc-marketing/blob/v1.3.0/pymc_marketing/mmm/components/adstock.py), [saturação PyMC](https://github.com/pymc-labs/pymc-marketing/blob/v1.3.0/pymc_marketing/mmm/components/saturation.py).

## Diagnósticos: política por contexto

R-hat, ESS bulk/tail, divergências, erro Monte Carlo e estabilidade por seed respondem perguntas diferentes. Robyn não tem R-hat. O worker Meridian auditado usa `az.summary` com arredondamento padrão e não devolve divergências nem ESS tail, embora a biblioteca possua `sample_stats.diverging`. Arredondar antes de aplicar limites mascara diferenças relevantes. O PyMC já usa `round_to='none'`, ESS bulk e contagem de divergências, mas falta ESS tail e auditoria dos parâmetros que foram excluídos do resumo.

Google documenta 1.2 como alerta em seus checks; Stan recomenda normalmente R-hat menor que 1.01 e quatro cadeias para uso mais confiável, discutindo sensibilidade ao problema. Nenhum desses números deve ser apresentado como lei universal ou garantia de identificação causal. Definir a política desta auditoria com justificativa e reportar métricas brutas; draws curtos não certificam convergência. Fontes: [saúde Meridian](https://developers.google.com/meridian/docs/post-modeling/health-checks), [diagnósticos Stan](https://mc-stan.org/learn-stan/diagnostics-warnings.html), [posterior analysis Stan](https://mc-stan.org/docs/reference-manual/analysis.html).

## Holdout e natureza da comparação

PyMC faz `fit(X[:cutoff], y[:cutoff])`, depois usa continuidade de adstock no posterior predictive. Isso é isolamento por prefixo na chamada auditada; ainda requer regressão de invariância de preprocessing e persistência. Meridian recomenda holdout balanceado e alerta que blocos contíguos finais podem ter knots mal estimados; seu modelo de baseline não foi desenhado para forecast do KPI. Uma competição de forecast na mesma cauda é um teste de estresse útil, mas não um ranking universal de qualidade MMM ou de efeito causal. Fonte: [holdout Meridian](https://developers.google.com/meridian/docs/advanced-modeling/holdout-observations).

## Procedência de datasets públicos

Nenhum dataset **oficial destes três projetos**, publicamente baixável e explicitamente comprovado como observações empresariais reais, foi confirmado nesta busca delimitada. Isso não prova inexistência. Não chamar dados de reais por aparência, nome de empresa fictícia ou postagem de terceiro.

| Exemplo oficial | Classificação verificável | Evidência primária |
|---|---|---|
| Meridian `geo_all_channels.csv` / exemplos hipotéticos | Simulado | [Notebook Google](https://developers.google.com/meridian/notebook/meridian-getting-started) identifica dataset como simulado. |
| Robyn `dt_simulated_weekly` | Simulado | [data.R oficial](https://github.com/facebookexperimental/Robyn/blob/main/R/R/data.R) identifica explicitamente dummy/simulado. |
| PyMC `mmm_example.csv`, exemplo end-to-end | Sintético | [Exemplo oficial](https://www.pymc-marketing.io/en/stable/notebooks/mmm/mmm_example.html) declara geração para recuperação de parâmetros; [quickstart](https://www.pymc-marketing.io/en/0.17.1/notebooks/mmm/mmm_quickstart.html) também identifica sintético. |

Portanto esses dados podem validar execução, recuperação sob DGP conhecido e robustez sob DGP divergente, mas não satisfazem uma etapa de validação com dados empresariais reais. Um relatório de caso sem dados liberados não resolve a disponibilidade nem autoriza acesso privado.

## Critérios de teste recomendados

1. Perturbar somente target holdout e verificar invariância das entradas escaladas de treino, priors efetivos e seleção de hiperparâmetros; distinguir invariância matemática de igualdade bit a bit de sampling paralelo.
2. Robyn: testar comprimentos efetivos 91, 94, 96, 99, 101 e 104, conferindo os limites nativos; nunca inferir teste pela fração arredondada sem comparar máscara.
3. Produzir baseline ingênuo e sazonal no mesmo conjunto de datas; métricas MAE/WAPE/R² em unidades iguais e denominadores explícitos, incluindo séries constantes/zero.
4. Diferenciar intervalo da média condicional de intervalo preditivo do observado; calcular cobertura somente quando a semântica coincidir.
5. Guardar versões, seeds, configuração efetiva e diagnósticos sem arredondar; rodar a carga adequada para cada motor, sem tentar ajustar volume apenas para obter aprovação.
6. Para causalidade, explicitar DAG/confundidores, estabilidade, suporte dos cenários e calibração experimental independente; qualidade preditiva isolada não basta.
