# Relatório MMM exploratório

Exploratory statistical association, not demonstrated causal attribution. Synthetic data do not establish market effectiveness. Simulations and any intervals are conditional on the model and assumptions; no real campaign or budget is changed.

Modelo: `model-6c5d6791c9074af6acaee0026e64876d`. Dataset: `demo-56b18635a4f2495bbb9bfd5375516a74`.
Motor: `constrained-ridge-v1`. Dados sintéticos: **True**.

## Desempenho temporal

| Conjunto | MAE | WAPE (%) | R² |
|---|---:|---:|---:|
| test | 98.243952 | 0.823815 | 0.976158 |
| test_train_mean_baseline | 723.465912 | 6.066554 | -0.185199 |
| train | 99.790345 | 0.813023 | 0.961357 |

## Método e proveniência

Split: `{"refit_on_test": false, "test_rows": 32, "test_start": "2025-05-19", "train_end": "2025-05-12", "train_rows": 116, "warmup_rows": 8}`.
Hash do dataset: `f20871a581c7a322de81412b1e599435e8ebff8d5e7289f93f5a86135fa5d5a2`.
Ajuste preditivo não demonstra atribuição causal nem eficácia de canais.

## Coeficientes

| Feature | Coeficiente |
|---|---:|
| cos_year | 11.58952255 |
| intercept | 9225.49136583 |
| price_index | -1965.92676248 |
| promotion | 588.34360489 |
| sin_year | 527.65606638 |
| spend_search | 3056.25867354 |
| spend_social | 3134.95674591 |
| spend_video | 3241.14094093 |
| trend_years | 196.88051168 |

## Incerteza

{"block_size": 4, "method": "moving_block_residual_bootstrap", "samples": 40, "scope": "conditional mean; fixed shape and inputs; not causal or predictive noise", "seed": 42}

## Diagnósticos e ressalvas

- FIXED_SHAPE: decay and Hill multiplier supplied, not estimated
- CONDITIONAL_HOLDOUT: test predictions use observed test spend and controls
- ZERO_INITIAL_STATE: prehistory unknown; warmup only approximates its removal
- CONDITIONAL_UNCERTAINTY: excludes shape, confounding and future input uncertainty

## Decisão

Usar como investigação condicional. Nenhuma campanha ou verba real foi alterada.
Calibração e validação empresarial exigem evidência experimental, origem autorizada e revisão humana.
