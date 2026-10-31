# Camada científica — auditoria e plano de execução

Base inspecionada em 31/10/2026: main `293828e`, árvore limpa; branch
`feat/scientific-validation`. Nenhum merge automático será realizado.

## Reuso e lacunas

| Área existente | Reuso | Ampliação necessária |
|---|---|---|
| diagnostics.classify_bayesian | R-hat/ESS/divergências e estados inconclusivos | MCSE relativo, cadeias inspecionáveis, PPC, política versionada |
| scientific.audit/backtest | Linhagem, decomposição, folds temporais e sensibilidade de forma Ridge | Protocolo para os quatro motores; regularização e repetições independentes |
| Workers Python/R | Runtimes isolados, formatos nativos, restauração, configurações efetivas | Diagnósticos por parâmetro, traços limitados e métricas de estabilidade |
| experiments | Poder, Welch/Newcombe/Fisher, SRM, perdas, guardrails, plano e hashes | Placebos/controles negativos, hipóteses explícitas e classificação da evidência |
| analysis.calibrate | Reponderação condicional de bootstrap Ridge | Exigir correspondência de estimando e proveniência para o novo protocolo |
| scientific_stress | Falhas sintéticas pontuais | Monte Carlo repetido, verdade conhecida, viés/RMSE/cobertura e erro Monte Carlo |
| get_analysis/export_analysis/dashboard | Contrato canônico e exportação | Três avaliações independentes e gráficos de diagnósticos |
| CI | 663 testes base e ciclos nativos curtos | Regressões adicionais e workflow científico extenso independente |

## Contratos e limites

O modo científico será aditivo a `audit_model`; o modo legado permanece disponível.
Relatórios são imutáveis, por tenant, armazenados como JSON com SHA256. IDs são
validados, sem caminhos ou URLs de entrada. `get_analysis` poderá consultar o
relatório correspondente e manterá diagnósticos antigos legíveis.

As classificações operacional, estatística e causal não se promovem mutuamente.
Ausência de evidência significa ausente/inconclusivo; erro observado significa
reprovação. Ridge e Robyn nunca recebem R-hat/ESS como critério de aceite.
Dados sintéticos nunca aprovam causalidade empresarial. R², contagem de draws e
cobertura de código não aprovam a adequação científica.

Testes MCMC curtos continuam classificados como transporte. O workflow extenso
usará quatro cadeias e amostragem adequada aos diagnósticos; falhas e avisos serão
preservados. PPC deve distinguir distribuição observada de média condicional.
Placebo não significativo não comprova ausência de confundimento; equivalência
exige margem predefinida e intervalo compatível. Declarações de randomização não
equivalem a auditoria independente da execução.

## Sequência

1. Regressões dos contratos e da separação das três avaliações.
2. Coleta nativa, protocolo de avaliação e estabilidade específica por motor.
3. Monte Carlo com sementes independentes, cenários adversos e denominadores completos.
4. Evidência experimental, placebos, controles negativos e calibração contextual.
5. MCP, dashboard, exportações e documentação.
6. Suíte completa, ciclos nativos possíveis, build, CI e PR com relatório factual.

## Referências oficiais consultadas

- https://mc-stan.org/docs/reference-manual/analysis.html
- https://mc-stan.org/rstan/reference/Rhat.html
- https://developers.google.com/meridian/docs/post-modeling/health-checks
- https://developers.google.com/meridian/docs/causal-inference/about-mmm-causal-inference-methodology
- https://facebookexperimental.github.io/Robyn/docs/features/
- https://www.pymc-marketing.io/en/latest/guide/mmm/mmm_learning_path.html

O gate interno será mais conservador que o resumo de saúde do Meridian, que usa
outro limiar de R-hat. Limiares são política documentada, não prova universal.
