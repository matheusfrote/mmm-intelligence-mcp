# Matriz de conformidade científica — 0.3.0

## Matriz atual V4

| Capacidade | Validação atual | Limite |
|---|---|---|
| MCP/base | 183 testes; 26 descobertas/23 chamadas/reinício | Windows/Python 3.12.14 nesta execução |
| CSV/qualidade | Parsing, fuso, agregação, negativas e original/hash | Sem conta real |
| Quatro motores | Recarga nativa e comparação em 30 datas comuns | MCMC curto inadequado; sem novo treino pesado |
| Futuro | Ridge variável/PyMC real após reinício | Meridian/Robyn indisponíveis |
| Incerteza | 60 ajustes, cobertura/recuperação medidas | Fronteira nula falha; cobertura não certificada |
| Painel | Chrome, números/CSV/JSON/CSP/navegação | Só Ridge; sem UI de treino |
| Segurança | HTTP real, tipos/Bandit/pip-audit/limites/hash | Não SaaS público; pacotes R fora de pip-audit |
| Distribuição/CI | Apache, CLI/wheel e workflows preparados | Sem release/PyPI/novo CI remoto |

[Matriz operacional detalhada](docs/v4-matrix.md) e [evidências](docs/validation/v4/README.md).
As matrizes anteriores abaixo são históricas.

Referências primárias consultadas e código das versões instaladas inspecionado: Meridian 2.1.0, PyMC-Marketing 1.3.0, Robyn 3.12.1/R 4.5.2. [Notas com links e provas originais](docs/scientific-official-references.md). Esta matriz descreve a implementação final; as notas registram também achados anteriores às correções.

| Dimensão | Local | Meridian | PyMC-Marketing | Robyn |
|---|---|---|---|---|
| Estimação | Ridge restrito SciPy | Bayes/MCMC nativo | Bayes/MCMC nativo | Ridge/Nevergrad nativo |
| Adstock | Geométrico normalizado, memória recursiva | Geométrico nativo, max lag 8 | Geométrico nativo, l_max 8 | Geométrico nativo |
| Saturação | Hill expoente 1 | Hill nativo | Logística nativa | Hill nativo |
| Formas | Declaradas ou seleção temporal interna | Priors defaults e posterior | Priors defaults e posterior | Busca por validação |
| Sinais mídia | Não negativos | Distribuições/parametrização nativas | Parametrização positiva de saturação | Positivos configurados |
| Exposição | Gasto | Gasto duplicado como proxy de exposição | Gasto | Gasto também em paid_media_vars |
| Holdout target | Não entra no ajuste/scalers | Placeholder de média do treino antes do loader; HoldoutSpec na likelihood | fit somente no prefixo | Placeholder somente no teste externo; validação verdadeira |
| Dados futuros conhecidos | Mídia/controles para previsão condicional | Mídia/controles históricos | Mídia/controles históricos | Mídia/controles históricos |
| Incerteza | Bootstrap residual em blocos, média condicional | Quantis de expected_outcome, média condicional | y_original_scale, preditivo observado | Pontual; intervalo indisponível |
| Diagnósticos | MAE/RMSE/WAPE/MAPE/R², posto, condição, resíduos | R-hat/ESS bulk e tail/divergências/indefinidos | R-hat/ESS bulk e tail/divergências/escopo | Métricas, seleção, trials/iterações |
| Persistência | JSON imutável + hash | Protobuf oficial | NetCDF oficial | JSON oficial; sem pickle/RDS |
| Futuro configurável | simulate_budget, 1–104 períodos | Adaptador expõe cenário histórico | Adaptador expõe cenário histórico | Resposta histórica por canal |
| Prova executada | 105 testes, MCP, stress/UI | Treino, consulta, recarga/cenário MCP | Treino, consulta, recarga/cenário MCP | Treino, consulta, recarga/cenário MCP + split R |
| Certificação causal | Não | Não | Não | Não |

As diferenças de transformação, baseline, warmup, teste e tipo de intervalo impedem interpretar as métricas como competição universal entre frameworks. Robyn usa 89/29/30 observações úteis; local usa 116/32 após warmup, enquanto os modelos Bayes usam prefixo 124/teste 32. A cauda contígua estressa previsão; a [documentação Meridian sobre holdout](https://developers.google.com/meridian/docs/advanced-modeling/holdout-observations) alerta sobre baseline e knots fora do suporte.

## Aprovação e limites

| Critério | Evidência | Estado |
|---|---|---|
| Matemática Ridge e gradientes | Testes independentes e diferenças finitas; [lsq_linear oficial](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.lsq_linear.html) | Aprovado funcionalmente |
| Isolamento do target reservado | Perturbação ×100; seleção nested; teste R real | Aprovado nos caminhos exercitados |
| Priors rastreáveis | Configuração efetiva salva no resultado nativo | Aprovado para rastreio; adequação contextual pendente |
| Sensibilidade de priors e recuperação causal | Não executada | Parcial/bloqueada para inferência empresarial |
| Saúde MCMC | R-hat/ESS/divergências publicados; [Stan](https://mc-stan.org/learn-stan/diagnostics-warnings.html) e [Google](https://developers.google.com/meridian/docs/post-modeling/health-checks) | Ajustes curtos reprovados para certificação |
| Intervalos calibrados | Tipos separados, coverage_certified=false | Não certificado |
| ROI/mROI incremental | Nenhum experimento de negócio | Indisponível; não substituir por contribuição/gasto |
| Otimização factível | Soma/limites/gradiente/malha; comparação com verba igual | Aprovado matematicamente; não é recomendação comercial |
| Confundimento e controle endógeno | Hipóteses e limites explícitos | Não resolvido automaticamente |

Regras operacionais de abstenção não são testes universais de validade. A ausência de alerta não autoriza decisão. As referências oficiais explicam métodos e contratos; não endossam este servidor ou seus resultados sintéticos.
