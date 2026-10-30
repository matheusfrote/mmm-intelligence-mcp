# Motor exploratório

## Transformações e ajuste

Para gasto `x[t] >= 0`, usamos adstock geométrico **normalizado**:

`a[t] = (1-d) * x[t] + d * a[t-1]`, com `0 <= d < 0.99` na API e `a[-1]=0`.

A normalização faz um gasto constante tender ao mesmo valor do gasto por período. Essa convenção difere da forma não normalizada `x[t]+d*a[t-1]`; não misture os seus K. A saturação aplicada depois do adstock é Hill com expoente fixo 1:

`h(a) = a / (K+a)`, `K > 0`.

Cada canal recebe `K = mediana dos adstocks positivos do treino após warmup * saturation_multiplier`. O parâmetro de retenção é fornecido e compartilhado entre canais. Não é estimado a partir da verdade do gerador; `tune_mmm` pode selecionar formas em validação interna, conforme a seção de extensões. Canal constante no treino bloqueia o ajuste por falta de variação. Controles constantes geram aviso.

A matriz inclui intercepto, mídia transformada, tendência em anos desde a origem, seno/cosseno anual e controles. O ajuste minimiza:

`||y - X*b||² + alpha * ||b_padronizado_sem_intercepto||²`

sujeito a coeficientes de mídia não negativos. Controles, tendência, sazonalidade e intercepto têm sinais livres. Preditores são padronizados pelas médias/desvios do treino; o intercepto não é penalizado. O solver `scipy.optimize.lsq_linear` recebe o sistema aumentado e os limites, e precisa convergir. Os coeficientes persistidos voltam à escala original das features para consulta e previsão. As estatísticas de padronização também são guardadas.

## Separação temporal

Com `n` linhas, o teste contém `ceil(n*test_fraction)` observações finais. As primeiras `warmup_periods` linhas alimentam adstock, mas não a regressão ou métricas. São exigidas pelo menos 26 linhas de treino úteis, mais do que features+5 quando maior, e cinco de teste. Esses mínimos são regras computacionais, não prova de suficiência para um MMM.

O modelo é ajustado uma vez no treino; não se reajusta após o teste. Transformações são temporais: cada estado depende do gasto atual e passado. Um teste altera target, gasto e controles futuros e exige coeficientes, K e escalas idênticos no ajuste. O holdout é **condicional** a gastos/controles realizados; não mede previsão ex ante dessas variáveis.

## Diagnósticos

- `MAE = média(|y - previsto|)`, na unidade do KPI.
- `WAPE_percent = 100 * soma(|y-previsto|) / soma(|y|)`; retorna null quando o denominador é zero.
- `R² = 1 - SSE/SST`; pode ser negativo e retorna null com alvo constante.
- Benchmark de teste: média do target do treino, sem observações futuras.
- Correlação residual de lag 1 no treino, posto da matriz e número de condição. São descritivos, não testes de identificação causal.

Há avisos para histórico anual curto, constantes, autocorrelação, condicionamento ruim e previsão negativa. Nenhum limiar de R²/WAPE certifica atribuição por canal. O split e as previsões completas são persistidos para auditoria.

## Simulação

O total do orçamento é dividido por `horizon` e distribuído pelas frações. O primeiro período futuro começa uma frequência após a última observação. A recorrência parte do **estado final observado**, incluindo o holdout, para cada canal. O comparador usa a média dos gastos das últimas até 13 observações, constante em todos os períodos. Ambos usam os mesmos controles e calendário futuros.

Sem `future_controls`, valores ficam constantes no último observado. Tendência/sazonalidade continuam a partir do índice temporal histórico. O retorno distingue previsão total, componente modelado de mídia, orçamento do comparador e diferença de previsões. Essa diferença não é lift causal nem lucro; quando os totais diferem, inclui também uma mudança no volume investido. O cliente de exemplo compara totais iguais.

Uma verba zero ainda pode apresentar componente de mídia por carryover histórico. Efeitos após o horizonte não entram no total. Orçamentos fora da faixa de gastos do treino geram aviso de extrapolação. optimize_budget calcula candidato numérico com limites, conforme a seção abaixo; não executa decisões em contas.

## Limitações explícitas

O motor Ridge não realiza inferência bayesiana. A versão 0.2 acrescenta bootstrap em blocos opcional, seleção temporal de formas e reponderação por experimento declarado; os motores externos fazem sua própria inferência. Geo pooling, alcance/frequência e correção automática de confundimento não observado não são expostos por esta API. O baseline linear pode extrapolar para valores negativos; não é recortado silenciosamente. O aquecimento de oito períodos não garante eliminar prehistória desconhecida. Formas e sinais restritos são hipóteses, não comprovação causal.

## Extensões da versão 0.2

`bootstrap_samples` de 1 a 500 habilita bootstrap de resíduos centrados em blocos móveis, somente no treino e com formas fixas. Cada amostra reajusta Ridge com mídia não negativa. A simulação usa os mesmos draws para cenário e referência, produzindo intervalos centrais de 90% do total médio e da diferença pareada. Isso não é intervalo preditivo completo: exclui incerteza da forma, controles futuros, confundimento e novos choques.

`tune_mmm` compara até 25 combinações de retenção/K em uma janela de validação interna anterior ao teste externo. Seleciona por MAE interno e reajusta no treino externo, deixando o teste externo sem participar da escolha. Rankings e datas são persistidos. Uma janela não substitui validação temporal repetida ou revisão substantiva; o teste prova que alterações no futuro externo não mudam o ranking.

`calibrate_experiment` exige pelo menos 20 draws de bootstrap e um experimento explicitamente declarado como sintético ou autorizado pelo host. Calcula a diferença de resposta ao gasto tratamento/controle, horizonte e estado inicial definidos; repondera os draws por uma verossimilhança gaussiana da estimativa de lift e seu erro padrão. Retorna média, intervalo e tamanho efetivo, sem substituir o modelo. É uma aproximação condicional, não um refit bayesiano nem certificação da randomização, identificação causal ou transporte do experimento.

`optimize_budget` resolve alocação de um total e limites por canal via SLSQP com gradiente analítico. Na família local Hill expoente 1 e mídia não negativa, a resposta é côncava na verba sob controles/estado fixos. O solver precisa satisfazer soma, limites e melhora sobre uma inicialização factível; testes comparam com malha independente. O resultado é um ótimo do modelo, sem garantia causal, de lucro ou de execução em plataformas.

A boa métrica da demonstração é esperada: gerador e estimador compartilham uma família de transformações. É teste de software e de invariantes, não validação de uma política comercial nem prova de recuperação verdadeira das contribuições.

## Auditoria 0.3

`audit_model` reconcilia a soma de intercepto, mídia, controles, tendência e sazonalidade com a previsão persistida; o resíduo separa observado e previsto. Esses componentes são associações ajustadas com carryover, não receita causal incremental. ROI/mROI ficam indisponíveis. Backtesting usa origens expansivas com janelas finais disjuntas; modelos tuned refazem seleção dentro de cada prefixo. Sensibilidade de formas não escolhe um vencedor pelo teste externo.

RMSE complementa MAE; MAPE exclui observados exatamente zero e informa a contagem. WAPE/R² retornam null com denominador indefinido. Posto e condicionamento padronizados separam escala de colinearidade; R² ajustado OLS é omitido por não representar graus de liberdade de Ridge restrito. Diagnósticos residuais são descritivos.

Bootstrap residual reajusta o estimador penalizado e pode deslocar os percentis por shrinkage. O ponto fora dos intervalos é sinalizado; não há recentramento artificial, posterior bayesiana ou cobertura certificada. Calibração exige mesma origem sintética/real do modelo e do experimento.

Otimização compara o candidato com uma referência de mesmo orçamento, horizonte, controles e estado inicial. Derivadas são KPI condicional por gasto. Sucesso SLSQP não gera recomendação de negócio: recommended_spend=null. Abstenção e revisão humana são explícitas, inclusive para dados sintéticos, posto deficiente, incerteza ausente, extrapolação ou instabilidade. [Auditoria e limites](../MMM_AUDIT_REPORT.md).

## Verificações V4

Viés = média(previsto - observado); valores positivos indicam superprevisão. R-hat
máximo deve ser menor que 1,01 e ESS bulk/tail mínimo pelo menos 100 por cadeia no
screen padrão. Esses dois limites são configuráveis em get_analysis. Quatro cadeias,
400 draws/tune são filtros operacionais de amostra, não prova universal de convergência.
Divergências/falhas conhecidas classificam como inadequado; informações ausentes ou
parâmetros indefinidos como inconclusivo; falha de estimação como não estimável.
Adequado significa apenas os screens avaliados; mistura, PPC, priors, estabilidade,
identificação e transporte exigem análise separada. Referência: [Stan](https://mc-stan.org/learn-stan/diagnostics-warnings.html).

examples/recovery_study.py executa seis regimes × dez seeds, 100 bootstraps por ajuste,
260 semanas, formas fixas por construção e coeficientes conhecidos 3000/1800/0. Controle
de preço negativo, tendência e sazonalidade pertencem ao DGP. Não há afirmação de que
formas foram aprendidas da verdade. Casos: bem especificado, ruído alto, colinearidade,
preço omitido, quebra estrutural e ruído assimétrico. Cobertura média condicional de
intervalos nominais 90%: 87,31%, 87,31%, 86,73%, 28,08%, 0% e 86,73%, respectivamente.
São dez replicações independentes por regime; datas dentro de cada série são dependentes.
Não estimar precisão Monte Carlo tratando todas as datas como replicações independentes.

No canal nulo, a cobertura paramétrica percentil foi zero: a restrição não negativa e
solução numérica na fronteira tornam o intervalo inadequado para testar efeito nulo.
Não arredondamos/recentramos limites para aparentar cobertura. uncertainty declara
supports_null_effect_testing=false e boundary_note. Além disso, colinearidade preservou
boa previsão sem recuperar os coeficientes separados. Esses resultados reforçam a
abstenção, não validam atribuição causal. Estudo pequeno não certifica cobertura geral.

A projeção PyMC usa a API nativa de posterior predictive com histórico intermediário
sem target; a Ridge usa estado terminal e bootstrap condicional. Detalhes e capacidades
em [comparison.md](comparison.md). [Estudo reproduzível](validation/v4/recovery.json).
