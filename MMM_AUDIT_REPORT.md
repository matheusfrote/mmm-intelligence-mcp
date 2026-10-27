# Auditoria científica e funcional — 0.3.0

## Atualização V4 — 26/10/2026

Diagnóstico e correções atuais em [v4-delivery](docs/v4-delivery.md). Novos contratos
preservam as semânticas dos quatro motores e classificam MCMC sem certificar causalidade.
Recargas nativas conferidas; modelos curtos Meridian/PyMC permanecem inadequados.
Sessenta ajustes controlados demonstraram subcobertura, falha na fronteira nula e
instabilidade sob especificação incorreta. Bootstrap não é teste de efeito nulo.
Nenhum dado empresarial foi usado; Strix encerrado conforme decisão do proprietário.
Os resultados anteriores abaixo permanecem históricos.

Auditoria de 25/10/2026. **Software local aprovado nos testes descritos; validade causal e uso empresarial não demonstrados.** O usuário autorizou dados fabricados por não possuir uma base real. Nenhum resultado sintético é apresentado como observação de mercado. Publicação de código não implica implantação de serviço.

## A. Conformidade científica

O motor local é Ridge com mídia não negativa, adstock geométrico normalizado e Hill de expoente 1. Meridian é bayesiano com Hill e priors próprios; PyMC usa adstock geométrico e saturação logística; Robyn combina Ridge, Hill, Nevergrad e objetivos múltiplos. São modelos distintos, não reproduções equivalentes. Nesta interface nacional não há inferência hierárquica entre geos. Gasto funciona como proxy declarado de exposição, sem impressões observadas. Consulte a [matriz](MMM_VALIDATION_MATRIX.md) e as [fontes oficiais inspecionadas](docs/scientific-official-references.md).

| Achado e risco | Correção e evidência |
|---|---|
| Target futuro influenciava o scaler Meridian antes da exclusão pela likelihood | Cópia das entradas substitui somente o target reservado pela média do treino; originais separados avaliam o teste. `HoldoutSpec` continua excluindo a cauda da likelihood. O scaler nativo inclui treino e placeholders; não se alega scaler ajustado apenas no prefixo. Teste de perturbação ×100 preserva as entradas. |
| Robyn calculava lambda usando target de teste externo; contagem aproximava o arredondamento nativo | Somente o target externo é mascarado antes dos inputs; validação verdadeira continua selecionando hiperparâmetros. Métricas do adaptador usam observados originais e datas nativas exatas. Testes Python e prova com helper R em 199 comprimentos, 52–250. |
| Backtest de modelo tuned poderia reutilizar formas escolhidas com futuro de um fold anterior | Seleção interna é refeita em cada prefixo; teste de regressão demonstra independência da cauda. |
| Priors e diagnósticos nativos incompletos ou arredondados | Configuração efetiva serializada; R-hat e ESS bulk/tail sem arredondamento, divergências, contagens indefinidas e escopo dos parâmetros. Não se certifica convergência. |
| Sucesso do otimizador confundido com recomendação | `optimal_spend` é candidato exploratório; `recommended_spend=null` e `business_recommendation_eligible=false`. Motivos e próximo passo são rastreáveis. |
| Advertências se perdiam na simulação; calibração misturava origens | Cenários herdam alertas; origem sintética/real deve coincidir entre modelo e experimento (`MIXED_DATA_ORIGINS`). |
| Bootstrap regularizado podia deslocar o centro dos draws | Viés de penalização e ponto fora dos percentis são registrados, sem recentramento artificial nem alegação de cobertura. |
| Condicionamento dependia das unidades; decomposição e comparação pouco auditáveis | Posto/condição padronizados, reconciliação de componentes, backtests, sensibilidade e referência com o mesmo orçamento/horizonte/controles/estado. |

## B. Dados utilizados

Somente dados construídos pelo gerador e variantes adversariais. Dataset principal: 156 semanas, 02/01/2023–22/12/2025; receita e moeda sintéticas. A [qualidade e procedência](MMM_DATA_QUALITY.md) registra definições, hash, casos inválidos e limites. Nenhuma conta de anúncios foi consultada para extrair dados. Não houve alteração de campanhas.

## C. MCP e segurança

16 ferramentas descobertas pelo cliente oficial. O ciclo stdio executa 13 ferramentas locais e verifica reinício; os três adaptadores completam `train_backend`, `get_backend_model` e `predict_backend` em processos reais. Não há fallback Ridge rotulado como outro motor. HTTP local tem autenticação, papéis e isolamento; armazenamento usa IDs, raízes autorizadas, hashes e criação sem sobrescrita. Testes cobrem travessia, links, corrupção, autorização e falhas estruturadas. [Contratos](docs/tools.md).

## D. Qualidade estatística

No exemplo Ridge, teste MAE 98,244, WAPE 0,824% e R² 0,976; média do treino tem MAE 723,466. Três janelas temporais disjuntas apresentam MAE 125,500 / 131,663 / 98,244. Isso é esperado em parte porque gerador e estimador compartilham família matemática. Não demonstra recuperação causal por canal.

A decomposição reconcilia previsões com erro máximo 3,64e-12. R² ajustado OLS não é calculado para Ridge restrito sem graus de liberdade apropriados. Durbin–Watson e autocorrelação são descritivos. Bootstrap estima incerteza condicional com formas/inputs fixos, não uma posterior ou cobertura certificada. Não se comparam intervalos de média Meridian com preditivos do observado PyMC como se tivessem a mesma semântica.

Os treinos nativos de verificação são curtos: Meridian tem R-hat máximo 1,257, ESS bulk mínimo 6,59 e uma divergência; PyMC tem R-hat 1,183 e ESS bulk 9,45. Ambos são inadequados para certificação inferencial. Robyn fez um trial/200 iterações, insuficiente para homologar busca empresarial. Os [resultados completos](MMM_VALIDATION_RESULTS.md) preservam esses achados; mais iterações isoladamente não provam identificação causal.

## E. Insights e abstenção

`audit_model` liga diagnóstico, evidência, hipótese, incerteza, ação, impacto condicional e validação proposta. Na demonstração, a fração numérica ótima de search varia de 13,59% a 35,44% entre nove especificações: amplitude 21,86 pontos percentuais. Isso aciona `SPECIFICATION_SENSITIVITY` no limiar operacional configurável de 20 pontos; não é intervalo de confiança nem limiar universal de validade. Nenhuma variante é escolhida pelo teste externo.

A ação sustentada é investigar definições, confundimento, correlação e estabilidade e planejar experimento de incrementalidade com população, KPI e horizonte previamente definidos. Não é aumentar um canal com base no ranking sintético. Impacto empresarial, ROI e mROI causais permanecem indisponíveis; derivadas condicionais do KPI por gasto são explicitamente distintas de lucro incremental. Casos de colinearidade, falta de incerteza, extrapolação e ausência de melhora frente ao baseline geram motivos adicionais de abstenção. Mesmo sem esses alertas, revisão humana continua obrigatória.

O dashboard mostra avisos e estimativas pontuais, sem propagar intervalos; a auditoria detalhada fica em JSON separado. A comparação JS/Python foi feita com os mesmos parâmetros, sem recursos externos. Não se alega homologação móvel abaixo da largura efetivamente observada de 500 px.

## F. Publicação e reprodução

Destino autorizado: [matheusfrote/mmm-intelligence-mcp](https://github.com/matheusfrote/mmm-intelligence-mcp), branch `main`. Fonte, testes, documentação e evidências sintéticas são publicáveis; ambientes, modelos binários, logs privados e configurações pessoais ficam excluídos. Estado de push e CI é registrado em [progresso](IMPLEMENTATION_PROGRESS.md) e no snapshot `docs/validation/scientific-github-ci.json` quando concluído. Sem PyPI, deploy ou endpoint público.

## G. Veredito por requisito

| Requisito | Classificação | Limite |
|---|---|---|
| Servidor, cinco ferramentas iniciais e 11 extensões | Aprovado funcionalmente | Escopo local documentado |
| Cálculos, métricas, temporalidade e restrições | Aprovado nos invariantes testados | Não prova modelo correto para toda empresa |
| Motores externos reais e persistência | Aprovado funcionalmente | Windows; CI base não instala os frameworks |
| Convergência dos ajustes MCMC curtos | Reprovado para uso inferencial | Diagnósticos insuficientes mantidos visíveis |
| Busca Robyn e sensibilidade de priors empresarial | Parcialmente validado | Busca reduzida; priors defaults persistidos, sem estudo contextual |
| Incerteza local e insight rastreável | Parcialmente validado | Condicional; cobertura/impacto empresarial não certificados |
| Dados empresariais e experimento real | Bloqueado por ausência de base | Usuário autorizou substituir execução por sintéticos |
| ROI/mROI causal e recomendação automática de verba | Não aprovado | Retorno causal indisponível; sistema se abstém |
| UI, segurança local e distribuição | Aprovado no escopo testado | Não inclui segurança corporativa ou advisories R completos |

Não restam correções conhecidas obrigatórias de software desta auditoria. Estudos de priors, convergência adequada, estabilidade por seeds, DAG/estimando e experimentos independentes permanecem trabalho analítico necessário antes de decisão real. Não são declarados implementados ou validados por estes testes.
