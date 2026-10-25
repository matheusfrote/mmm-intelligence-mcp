# Contrato das ferramentas

Atualização 0.3: há 16 ferramentas e o cliente oficial é SDK MCP 2.3. Os nomes Python do cliente são `structured_content` e `is_error`; o JSON do protocolo preserva seus aliases de wire. O envelope `ok/data/error` continua.

Robyn exige `test_fraction=0.2`, correspondente ao split nativo 60/20/20 e seu arredondamento; outros valores falham na validação antes de iniciar worker. `tune_mmm` valida toda a série, incluindo o holdout externo, sem usar o holdout para selecionar hiperparâmetros. Calibração cujo erro padrão/lift exceda o intervalo numérico retorna `CALIBRATION_NUMERIC_RANGE`, sem apresentar NaN como sucesso.

Cada chamada tem `arguments = {"request": {...}}`. IDs: 1–64 caracteres ASCII minúsculos, números, `_` e `-`, começando com letra/número. Nomes reservados do Windows são bloqueados pela persistência. IDs ausentes nas criações são gerados com UUID. Toda criação é imutável; para nova versão, use outro ID.

## Entradas

| Ferramenta | Obrigatório | Opcionais e padrões |
|---|---|---|
| generate_demo_dataset | nenhum | dataset_id=null; periods=156 (52–10000); seed=42 (0..2³²−1); start_date=2023-01-02; frequency=weekly ou daily |
| validate_dataset | dataset_id | media_columns, control_columns, target_column, date_column, test_fraction=0.2, warmup_periods=8 |
| train_mmm | dataset_id | mesmos campos do validador; model_id=null; ridge_alpha=0.1; adstock_decay=0.5; saturation_multiplier=1.0 |
| get_model | model_id | nenhum |
| audit_model | model_id | folds=3 (2–5), decays=[0.2,0.5,0.8], multipliers=[0.5,1,2], max_allocation_spread=0.2 (0–1) |
| simulate_budget | model_id, total_budget, allocation | horizon=13 (1–104 períodos); future_controls=null |
| import_dataset | rows, synthetic, authorization_reference | dataset_id; frequency=weekly; units; schema de colunas; target_type=unspecified; data_context={} |
| optimize_budget | model_id, total_budget | horizon=13; lower/upper, limites totais por canal; future_controls |
| tune_mmm | dataset_id | mesmos campos de treino; decays=[0.2,0.5,0.8]; multipliers=[0.5,1,2] |
| calibrate_experiment | model_id, channel, treatment_spend, control_spend, lift_mean, lift_sd, experiment_id, synthetic | horizon=4; initial_adstock=0 |
| render_dashboard / generate_report | model_id | artifact_id automático |
| backend_status | nenhum | request={} |
| train_backend | dataset_id, backend | model_id; draws=100; tune=100; chains=2; seed=42; schema/split |
| get_backend_model | model_id | nenhum |
| predict_backend | model_id | media_multiplier={}, cenário histórico nativo |

O treino local aceita `bootstrap_samples=0` (0–500), `bootstrap_block_size=4` (1–26) e `bootstrap_seed=42`. Com draws, a simulação devolve intervalos centrais condicionais de 90% da média; calibração exige pelo menos 20 draws. A seleção de formas admite até 25 combinações e preserva o teste externo. Veja [método](methodology.md).

`audit_model` é leitura com custo computacional limitado: reconstrói a linhagem pelo hash, componentes aditivos e intervalos condicionais; executa folds temporais disjuntos (seleção nested quando tuned) e até 25 especificações. Faixas de alocação são sensibilidade, não confiança. `max_allocation_spread` é um alerta operacional configurável, não limiar universal de validade. Históricos insuficientes produzem backtest indisponível e abstenção explícita. O contrato não fornece ROI/mROI causal: esses campos são null.

`optimize_budget` devolve `optimal_spend` como candidato numérico, `recommended_spend=null`, `decision_support`, comparação de mesmo total, diferenças absolutas/percentuais da referência e derivadas condicionais `marginal_kpi_per_spend`. Não são lucro ou mROI causal. Alertas do modelo acompanham cenários. Calibração recusa origens sintéticas/reais diferentes (`MIXED_DATA_ORIGINS`).

`target_type` aceita revenue/non_revenue/unspecified. `data_context` aceita até 12 campos textuais com até 1000 caracteres por valor. Meridian exige revenue declarado; Robyn exige tipo conhecido para revenue/conversion; PyMC aceita KPI genérico. Não inferir receita apenas pelo nome da coluna. As exceções legadas aplicam-se somente ao gerador conhecido, documentado no artefato.

Motores aceitos: `google_meridian`, `pymc_marketing`, `meta_robyn`. As duas primeiras opções usam draws/tune/chains; Robyn faz ao menos 200 iterações/um trial com mídia positiva e seleção por validação. Modelos externos ficam em namespace separado; consulte-os por `get_backend_model`. Cenários não substituem universalmente o horizonte futuro local: Meridian exige dimensões históricas; Robyn com multiplicadores devolve respostas por canal. Nenhum número vem de fallback Ridge.

Padrões de colunas: target `revenue`, data `date`, mídias `spend_search`, `spend_social`, `spend_video`; controles `price_index`, `promotion`. Aceitam-se 1–10 mídias e 0–10 controles, distintos, sem usar target/data como features. Nomes de features internos são reservados. Ao validar um schema personalizado, forneça os mesmos campos ao treinar.

Desde 0.3.1, nomes de target/data seguem a mesma regra lexical das mídias/controles: letra ASCII inicial, letras/números/underscore e até 64 caracteres. Sintaxe de fórmula, caminhos e nomes excessivos são recusados antes de acessar dados ou workers.

`test_fraction` entre 0.1 e 0.4; `warmup_periods` 0–52; `ridge_alpha` >0 e <=10000; `adstock_decay` >=0 e <0.99; `saturation_multiplier` >0 e <=100. O orçamento total é finito, entre 0 e 1e9, na unidade monetária do dataset. Frações de allocation são finitas, entre 0 e 1, somam 1 com tolerância 1e-8 e nomeiam exatamente as mídias do modelo. Controles futuros exigem exatamente os controles modelados e vetores de tamanho igual ao horizonte, números finitos com magnitude até 1e12.

Dataset tem metadata `synthetic`, `frequency` e `rows`. Datas são ISO YYYY-MM-DD, crescentes e sem repetição, a passos exatos de um ou sete dias. Colunas numéricas exigidas não aceitam null, texto, booleano, NaN/Inf ou magnitude acima de 1e12. Target e gastos não podem ser negativos. O servidor não ordena, imputa nem remove linhas automaticamente. A declaração sintética é metadata local confiada ao operador; não é perícia da origem.

## Saída

```json
{
  "schema_version": "1.0",
  "ok": true,
  "exploratory": true,
  "disclaimer": "Exploratory statistical association, not demonstrated causal attribution. ...",
  "data": {},
  "error": null,
  "warnings": []
}
```

No protocolo, a resposta está em `structuredContent`, além da representação textual produzida pelo SDK. Campos internos de `data` variam conforme a ferramenta. Eles contêm IDs/hashes, relatório de validação, resumo de ajuste, modelo completo ou cenário. O esquema de envelope é tipado; os detalhes de `data` são objetos JSON documentados e versionados com o artefato.

As renderizações persistem um artefato imutável e devolvem também o conteúdo completo para exportação local. Modelos externos omitem os bytes nativos na consulta pública, mas preservam parâmetros/diagnósticos/previsões/procedência no armazenamento interno. A ferramenta de status não equivale a importar a biblioteca ou provar convergência.

**Erros de domínio** retornam `ok=false`, `data=null`, `error={code,message}`, mantendo o envelope e a ressalva. Nesta versão, seu `CallToolResult.isError` pode ser false: o cliente precisa verificar **`ok`**. **Erros de entrada detectados pelo SDK** retornam `isError=true` no protocolo, antes da aplicação, sem garantia de envelope. O cliente de exemplo testa ambos os fluxos.

Validação concluída não significa dataset válido: `validate_dataset` pode retornar `ok=true` com **`data.valid=false`**, acompanhado de `issues`. Treinamento bloqueia esse dataset com `DATASET_INVALID`.

| Código | Condição |
|---|---|
| INPUT_INVALID / INVALID_ID | Campo inválido ou ID proibido |
| NOT_FOUND / ALREADY_EXISTS | Ausência ou tentativa de sobrescrita |
| REAL_DATA_DISABLED | Origem não marcada como sintética sem autorização do host |
| DATASET_INVALID / UNIDENTIFIABLE_MEDIA | Dados fora do contrato ou mídia sem variação no treino |
| UNSAFE_PATH | Link, junction, reparse point, hard link na leitura ou saída da raiz |
| CORRUPT_ARTIFACT / CORRUPT_MODEL | JSON, hash, versão, parâmetros ou dimensões inválidas |
| ARTIFACT_TOO_LARGE / ROW_LIMIT | Limite de armazenamento/linhas |
| CHANNEL_MISMATCH / CONTROL_MISMATCH | Cenário não corresponde ao modelo |
| SOLVER_FAILED / NUMERICAL_ERROR | Ajuste sem convergência ou previsão não finita |
| INVALID_DATA / STORAGE_ERROR / INTERNAL_ERROR | Falha de valores/datas, IO local ou falha inesperada |

Logs da aplicação associam falhas a um identificador de evento e código, sem copiar o payload ou detalhes internos de exceções. A aplicação não devolve tracebacks ao cliente.
