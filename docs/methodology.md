# Motor exploratório

## Transformações e ajuste

Para gasto `x[t] >= 0`, usamos adstock geométrico **normalizado**:

`a[t] = (1-d) * x[t] + d * a[t-1]`, com `0 <= d < 0.99` na API e `a[-1]=0`.

A normalização faz um gasto constante tender ao mesmo valor do gasto por período. Essa convenção difere da forma não normalizada `x[t]+d*a[t-1]`; não misture os seus K. A saturação aplicada depois do adstock é Hill com expoente fixo 1:

`h(a) = a / (K+a)`, `K > 0`.

Cada canal recebe `K = mediana dos adstocks positivos do treino após warmup * saturation_multiplier`. O parâmetro de retenção é fornecido e compartilhado entre canais. Não é estimado a partir da verdade do gerador; não há busca ou calibração de formas nesta versão. Canal constante no treino bloqueia o ajuste por falta de variação. Controles constantes geram aviso.

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

Uma verba zero ainda pode apresentar componente de mídia por carryover histórico. Efeitos após o horizonte não entram no total. Orçamentos fora da faixa de gastos do treino geram aviso de extrapolação. Não existe otimização automática nesta versão.

## Limitações explícitas

O motor Ridge não realiza inferência bayesiana. A versão 0.2 acrescenta bootstrap em blocos opcional, seleção temporal de formas e reponderação por experimento declarado; os motores externos fazem sua própria inferência. Geo pooling, alcance/frequência e correção automática de confundimento não observado não são expostos por esta API. O baseline linear pode extrapolar para valores negativos; não é recortado silenciosamente. O aquecimento de oito períodos não garante eliminar prehistória desconhecida. Formas e sinais restritos são hipóteses, não comprovação causal.

## Extensões da versão 0.2

`bootstrap_samples` de 1 a 500 habilita bootstrap de resíduos centrados em blocos móveis, somente no treino e com formas fixas. Cada amostra reajusta Ridge com mídia não negativa. A simulação usa os mesmos draws para cenário e referência, produzindo intervalos centrais de 90% do total médio e da diferença pareada. Isso não é intervalo preditivo completo: exclui incerteza da forma, controles futuros, confundimento e novos choques.

`tune_mmm` compara até 25 combinações de retenção/K em uma janela de validação interna anterior ao teste externo. Seleciona por MAE interno e reajusta no treino externo, deixando o teste externo sem participar da escolha. Rankings e datas são persistidos. Uma janela não substitui validação temporal repetida ou revisão substantiva; o teste prova que alterações no futuro externo não mudam o ranking.

`calibrate_experiment` exige pelo menos 20 draws de bootstrap e um experimento explicitamente declarado como sintético ou autorizado pelo host. Calcula a diferença de resposta ao gasto tratamento/controle, horizonte e estado inicial definidos; repondera os draws por uma verossimilhança gaussiana da estimativa de lift e seu erro padrão. Retorna média, intervalo e tamanho efetivo, sem substituir o modelo. É uma aproximação condicional, não um refit bayesiano nem certificação da randomização, identificação causal ou transporte do experimento.

`optimize_budget` resolve alocação de um total e limites por canal via SLSQP com gradiente analítico. Na família local Hill expoente 1 e mídia não negativa, a resposta é côncava na verba sob controles/estado fixos. O solver precisa satisfazer soma, limites e melhora sobre uma inicialização factível; testes comparam com malha independente. O resultado é um ótimo do modelo, sem garantia causal, de lucro ou de execução em plataformas.

A boa métrica da demonstração é esperada: gerador e estimador compartilham uma família de transformações. É teste de software e de invariantes, não validação de uma política comercial nem prova de recuperação verdadeira das contribuições.
