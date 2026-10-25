# Relatório MMM exploratório

Exploratory statistical association, not demonstrated causal attribution. Synthetic data do not establish market effectiveness. Simulations and any intervals are conditional on the model and assumptions; no real campaign or budget is changed.

Modelo: `model-fc2fa406cac6432986cca8a9086b3c8b`. Dataset: `demo-e926fd927e93463aa50bbf486edad2c7`.
Motor: `constrained-ridge-v1`. Dados sintéticos: **True**.

## Desempenho temporal

| Conjunto | MAE | RMSE | WAPE (%) | MAPE sem zeros (%) | R² |
|---|---:|---:|---:|---:|---:|
| test | 98.243952 | 125.041560 | 0.823815 | 0.821439 | 0.976158 |
| test_train_mean_baseline | 723.465912 | 881.620492 | 6.066554 | 6.264763 | -0.185199 |
| train | 99.790345 | 125.083475 | 0.813023 | 0.819169 | 0.961357 |

## Método e proveniência

Split: `{"refit_on_test": false, "test_rows": 32, "test_start": "2025-05-19", "train_end": "2025-05-12", "train_rows": 116, "warmup_rows": 8}`.
Hash do dataset: `43ab06c77a76626f99ba135c46eef0b11696b53bc7fe4acb9a6d5319cef22e88`.
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

{"block_size": 4, "coverage_certified": false, "method": "moving_block_residual_bootstrap", "penalty_bias_note": "Residual bootstrap refits the penalized estimator; shrinkage can shift draws. Not a Bayesian posterior.", "point_outside_percentile_interval": [], "samples": 40, "scope": "conditional mean; fixed shape and inputs; not causal or predictive noise", "seed": 42}

## Diagnósticos e ressalvas

- FIXED_SHAPE: decay and Hill multiplier supplied, not estimated
- CONDITIONAL_HOLDOUT: test predictions use observed test spend and controls
- ZERO_INITIAL_STATE: prehistory unknown; warmup only approximates its removal
- MEDIA_SIGN_RESTRICTION: nonnegative conditional media coefficients are an explicit modeling assumption
- CONDITIONAL_UNCERTAINTY: excludes shape, confounding and future input uncertainty

## Validade da decisão

Sucesso numérico não autoriza realocação. Receita modelada não é receita causal incremental; ROI/mROI causal não foram demonstrados.
{"status": "abstain_from_budget_change", "business_recommendation_eligible": false, "reasons": ["SYNTHETIC_DATA"], "policy": "Conservative evidence screens, not universal statistical acceptance thresholds. Numeric optimization remains an exploratory candidate.", "required_next_step": "Review business context, causal assumptions, stability and experiment evidence before any budget change"}

Diagnósticos descritivos (sem certificação de independência ou identificação causal):
{"adjusted_r2": null, "adjusted_r2_reason": "Nominal OLS degrees of freedom are inappropriate for constrained regularized regression", "condition_number": 106.5641257114328, "feature_count": 9, "matrix_rank": 9, "residual_diagnostics_scope": "descriptive; no causal or independence certification", "standardized_condition_number": 1.7765839982996927, "standardized_matrix_rank": 9, "train_durbin_watson": 1.9706333735406416, "train_residual_lag1": -0.016333144516447243, "train_residual_mean": -3.982959556040065e-12}

Execute audit_model para decomposição reconciliada, backtesting temporal, sensibilidade e insight rastreável.

## Decisão

Usar como investigação condicional. Nenhuma campanha ou verba real foi alterada.
Calibração e validação empresarial exigem evidência experimental, origem autorizada e revisão humana.
