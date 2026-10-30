# Contrato canônico e comparação

`get_analysis` preserva backend/versão, configuração efetiva, request/seed, hash do
dataset, KPI/unidades/frequência, datas de treino/teste, observado/previsto, métricas,
baseline de média do treino, diagnósticos, intervalos e capacidades. O artefato nativo
permanece armazenado; seus bytes não são enviados nessa análise. Os motores mantêm
transformações, priors, parâmetros e escalas próprios.

| Operação | Ridge | PyMC-Marketing | Meridian | Robyn |
|---|---|---|---|---|
| Treino/recarga/holdout | Sim | Runtime opcional | Runtime opcional | Python + R opcionais |
| Projeção futura/plano variável | Sim | Sim | Indisponível no adapter | Indisponível no adapter |
| Otimização com limites | Candidato numérico | Indisponível | Indisponível | Indisponível |
| Calibração exposta | Bootstrap reponderado | Indisponível | Indisponível | Indisponível |
| Análise/exportação/comparação | Sim | Sim | Sim | Sim |
| Dashboard local | Sim | Indisponível | Indisponível | Indisponível |
| Geo/causalidade certificada | Não | Não nesta API | Não nesta API | Não nesta API |

Capacidade no código não comprova runtime instalado. doctor/backend_status verificam
presença; execução nativa comprova bibliotecas. model_capabilities distingue operações.

`compare_models` recebe 2–5 modelos distintos e exige mesmo hash de dataset, KPI, tipo,
canais, frequência e unidades. `window_policy=exact` exige todas as datas de teste iguais.
`intersection` requer opção explícita e pelo menos cinco datas comuns. Métricas e
intervalos são alinhados às datas comuns; treino diferente é sinalizado e suas datas
são retornadas. `same_training_window` mede apenas datas; `fair_training_protocol=null`
evita certificar equidade de informação, busca ou priors. `winner=null` impede eleger
um vencedor universal pelo erro em um único dataset.

Na V4, três artefatos nativos existentes e um novo Ridge compartilharam o mesmo dataset
sintético. A janela exata foi recusada porque Robyn usa split/arredondamento próprios;
a interseção tinha 30 períodos. Meridian/PyMC apresentaram diagnósticos inadequados.
Esses resultados verificam o software e não justificam escolha comercial de motor.

```json
{"request":{"models":[{"backend":"ridge","model_id":"fit-a"},{"backend":"pymc_marketing","model_id":"fit-b"}],"window_policy":"intersection"}}
```

`forecast_model` exige media_plan e future_controls completos, vetores do mesmo
horizonte de 1–104 períodos e gasto total até 1e9. Começa após a última observação;
controles não são copiados implicitamente. Ridge continua estado terminal, tendência
e sazonalidade. PyMC restaura NetCDF, acrescenta mídia/controles entre treino e última
observação, usa include_last_observations e retorna somente o futuro. Targets de
holdout/futuro não atualizam o modelo. O intervalo total é calculado da soma dos draws,
nunca pela soma dos limites marginais. Extrapolação de gasto é sinalizada.

PyMC retorna posterior preditiva observada; Ridge retorna média condicional por
bootstrap. Nenhum intervalo incorpora todos os erros de especificação/inputs futuros.
Otimização nativa exige contrato próprio de baseline, horizonte, carryover, restrições
e incerteza. InvestmentOptimizer/BudgetConstraints permanecem interfaces de extensão.
Não há fallback Ridge com rótulo nativo. Forecast Meridian/Robyn e otimização externa
são pendências de implementação/validação metodológica, não bloqueios de credencial.
