# Resultados da validação científica — 31/10/2026

Esta entrega parte de `main` (`293828e`) e preserva o servidor de 45 ferramentas,
o recurso e os prompts existentes. A camada é aditiva em `audit_model`,
`get_analysis`, exportações e dashboard. Não houve uso de dados reais, mudança
de campanhas, deploy ou merge automático.

## Escopo comprovado e interpretação

| Avaliação | Evidência executada | Resultado científico |
|---|---|---|
| Ridge | Solver real, regularização, omissão de controle, backtests e 1.000 repetições em dez DGPs | Operacional aprovado; incerteza reprovada por subcobertura no efeito nulo |
| Meridian | Ajuste nativo, restauração, quatro cadeias de 1.000 draws após 1.000 warmup, PPC e três refits | Operacional aprovado; PPC reprovado; convergência completa inconclusiva por nove diagnósticos indefinidos |
| PyMC-Marketing | Mesmo orçamento de amostragem, restauração, PPC; três refits no relatório recuperado | Operacional aprovado; MCSE e PPC reprovados apesar de R-hat/ESS compatíveis |
| Robyn | Ciclo nativo curto com três refits; busca extensa de cinco trials × 2.000 iterações | Operacional aprovado; critérios nativos da busca reprovados; refits com orçamento extenso permanecem ausentes |
| Causalidade | Experimentos fabricados, testes de placebo/controle negativo, hipóteses, linhagem e calibração condicional | Somente simulação; nenhum efeito de campanha real certificado |

O protocolo relata falhas em vez de ajustar critérios depois de observar os
resultados. Aprovação operacional não promove o estado estatístico ou causal.
Nenhum dos exemplos autoriza recomendação automática de investimento.

## Monte Carlo Ridge

O piloto usou semente 42. A análise final usa uma nova semente 73, após tornar
explícita a política de aceitação de intervalos. Cada cenário tem 100 tentativas;
as 200 rejeições esperadas de KPI ausente/investimento constante permanecem
registradas. O estimando é o lift médio no holdout sob aumento histórico de 10%
em um canal, incluindo carryover. Os valores abaixo são do canal search, em
unidades do KPI sintético; os três canais estão no JSON.

| DGP | Viés | RMSE | Cobertura de intervalo nominal 90% | Falhas / 100 |
|---|---:|---:|---:|---:|
| Bem especificado | 0,046 | 4,079 | 85% | 0 |
| Efeito nulo | 1,564 | 2,927 | 0% | 0 |
| Colinearidade | -6,003 | 6,448 | 10% | 0 |
| Confundidor omitido | 142,668 | 144,876 | 0% | 0 |
| Ruptura de tracking | -18,885 | 19,408 | 0% | 0 |
| Caudas pesadas | 0,022 | 6,301 | 83% | 0 |
| Adstock mal especificado | -32,081 | 32,557 | 0% | 0 |
| Variação fraca | 893,950 | 1.658,351 | 97% | 0 |
| KPI ausente | Indisponível | Indisponível | Indisponível | 100 |
| Investimento constante | Indisponível | Indisponível | Indisponível | 100 |

O cenário de variação fraca ilustra por que cobertura alta não basta. O cenário
nulo expõe a limitação do bootstrap residual condicional com coeficientes
restritos. Essa constatação está incorporada à classificação, sem substituir
silenciosamente o estimador. Limites substantivos de viés/RMSE ainda precisam ser
pré-especificados para qualquer aprovação; não foram escolhidos retrospectivamente.
Consulte [Ridge: métricas, MCSE, Wilson e política](validation/scientific/ridge.json).

## Diagnósticos Bayesianos observados

| Métrica | Meridian | PyMC-Marketing |
|---|---:|---:|
| Maior R-hat finito | 1,00993 | 1,00520 |
| Menor ESS bulk finito | 922,0 | 789,6 |
| Menor ESS tail finito | 1.027,0 | 470,2 |
| Divergências | 0 | 0 |
| Maior MCSE média / SD definido | 0,03309 | 0,05624 |
| Cobertura pontual PPC 90% no holdout | 3,125% | 37,5% |

Os R-hats/ESS acima descrevem somente valores finitos. No Meridian nacional,
nove componentes constantes (`eta_m`, `slope_m`, `xi_c`, referência `tau_g`)
produziram R-hat/MCSE indefinidos. Permanecem visíveis; não foram descartados para
obter aprovação. A distinção automática entre parâmetros declaradamente fixos e
cadeias livres travadas é uma extensão pendente. Os traços existem para inspeção
humana, sem certificação automática de mistura.

A execução extensa original do PyMC atingiu o limite de comunicação do cliente,
mas o servidor concluiu e persistiu o relatório, incluindo três refits. A
recuperação verificou hashes e registrou explicitamente a ausência da resposta
original. Uma nova execução via SDK restaurou o mesmo modelo e repetiu o
diagnóstico/PPC sem refits. Esses eventos são distintos:
[relatório recuperado](validation/scientific/pymc-extensive-recovered.json),
[reauditoria via SDK](validation/scientific/pymc_marketing.json) e
[Meridian com refits](validation/scientific/google_meridian.json).

## Limites e dependências externas

- A suíte Monte Carlo de efeitos com verdade conhecida avalia Ridge. Estudos
  equivalentes para parametrizações nativas, com estimandos compatíveis, ainda
  precisam ser desenhados e executados; intervalos de previsão não os substituem.
- Sensibilidade cobre sementes, regularização, formas Ridge e omissão de controle;
  não esgota famílias de priors, likelihoods ou desenhos geográficos.
- A primeira busca Robyn de cinco trials × 2.000 iterações expirou no limite
  interno antigo de 850 segundos, perto de 91% da primeira etapa. O limite foi
  corrigido e recebeu regressão automatizada. A repetição concluiu pelo SDK, com
  fontes inalteradas durante a execução, restauração e exportação verificadas.
  Seus critérios nativos sinalizaram `DECOMP.RSSD NOT converged` (mediana) e
  `NRMSE NOT converged` (dispersão). A classificação preserva essa reprovação;
  não usa diagnósticos MCMC para Robyn. Os três refits do teste de transporte usam
  orçamento reduzido; a repetição extensa foi feita com `--skip-refits` e não
  comprova estabilidade no mesmo orçamento. Consulte o
  [recibo Robyn](validation/scientific/meta_robyn.json). A primeira falha de
  execução, isoladamente, não era convergência nem evidência estatística negativa.
- Experimentos reais, autenticidade da randomização, interferência, confundimento,
  transportabilidade e unidades econômicas exigem dados e revisão independentes.
- A calibração implementada é reponderação condicional de draws Ridge com lift/SE
  derivados do experimento. Não é refit Bayesiano nativo nem integração GeoX.
- Fixtures do dashboard incluem relatórios sintéticos anteriores para verificar
  leitura de versões legadas. Não representam aprovação do protocolo atual.

## Reprodução e evidências

Verificações de software concluídas na revisão das fontes registrada no
[recibo consolidado](validation/scientific/software-verification.json):

| Verificação | Resultado observado |
|---|---|
| Regressão Windows | 724 aprovados; três ciclos nativos executados separadamente |
| Regressão Linux em contêiner sem rede | 722 aprovados; três nativos e um teste exclusivo Windows omitidos pela plataforma |
| Ciclos nativos reais | 3 aprovados, sem substituição por mocks |
| Python, agregado Windows/Linux/workers com hashes iguais | 4.227/4.227 linhas e 1.554/1.554 decisões |
| Dashboard real no Chrome | Aprovado; 834/834 linhas, 306/306 decisões JavaScript |
| Worker R | 100% das expressões executáveis covr e 22/22 decisões/laços AST; não é MC/DC |
| Cliente MCP oficial stdio | 45 ferramentas, um recurso, três prompts e reinício aprovados |
| HTTP e isolamento de acesso | Aprovados; endpoint MCP protegido e dashboard local direto |
| Wheel em ambiente novo | Instalação, origem do import, comando, 45 ferramentas e reinício aprovados |
| Contêiner de produção local | Usuário sem privilégio, sem rede/portas publicadas; acesso e reinício aprovados |
| Análises estáticas e dependências | Ruff, mypy (45 módulos), Bandit, pip check, auditorias pip/npm e busca de padrões de segredos aprovados |

O Windows preservou um aviso numérico SciPy já observado no teste de backtest
anterior; seus invariantes passaram. O Linux registrou aviso de permissão de cache
pytest no bind mount, sem falha dos testes. Os recibos não equivalem à matriz
completa do GitHub Actions; o estado remoto deve ser consultado na PR.

O primeiro CI remoto aprovou os demais 24 checks, mas bloqueou a instalação R por
divergência de SHA256. A conferência dos 115 downloads CRAN encontrou 101 outras
divergências nas URLs das mesmas versões, além de QuickJSR. A investigação
detalhada de QuickJSR confirmou apenas
metadados de build na DLL, sem alteração de suas seções de código/dados; isso não
foi usado para desativar hashes ou aprovar todos os arquivos reconstruídos.
A instalação passou a usar o snapshot oficial Posit CRAN de **23/10/2026**, que
preserva exatamente as 115 versões. Todos os ZIPs foram conferidos por versão,
fixados por SHA256 e instalados em biblioteca separada. Os casos nativos R de
treino, restauração, cenários, legado e conversões passaram novamente, com 100%
das expressões do worker. O cache é separado por snapshot; `latest` é recusado.
Os recibos científicos anteriores continuam associados à instalação original.
Consulte a [investigação e validação do snapshot](validation/scientific/r-upstream-rebuild.json)
e a documentação oficial de [snapshots](https://packagemanager.posit.co/__docs__/admin/repositories.html)
e [binários](https://packagemanager.posit.co/__docs__/admin/serving-binaries.html).

[Protocolo e comandos](scientific-validation.md) descrevem os parâmetros, limites
e workflow manual extenso. [Ambiente](validation/scientific/environment.json)
registra versões dos runtimes, locks e conferência dos pacotes R instalados.
Os JSONs selecionam campos dos resultados reais, sem alterar métricas ou estados,
e registram hashes do recibo completo, dados, modelo, fontes e configurações.
Recibos completos e artefatos nativos ficam em `evidence/` local, ignorados pelo
Git; são reproduzíveis pelo cliente MCP oficial. Uma execução bem-sucedida pode
corretamente produzir reprovação ou conclusão inconclusiva.
