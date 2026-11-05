# Resultados da validaÃ§Ã£o cientÃ­fica â€” 31/10/2026

Esta entrega parte de `main` (`293828e`) e preserva o servidor de 45 ferramentas,
o recurso e os prompts existentes. A camada Ã© aditiva em `audit_model`,
`get_analysis`, exportaÃ§Ãµes e dashboard. NÃ£o houve uso de dados reais, mudanÃ§a
de campanhas, deploy ou merge automÃ¡tico.

## Escopo comprovado e interpretaÃ§Ã£o

| AvaliaÃ§Ã£o | EvidÃªncia executada | Resultado cientÃ­fico |
|---|---|---|
| Ridge | Solver real, regularizaÃ§Ã£o, omissÃ£o de controle, backtests e 1.000 repetiÃ§Ãµes em dez DGPs | Operacional aprovado; incerteza reprovada por subcobertura no efeito nulo |
| Meridian | Ajuste nativo, restauraÃ§Ã£o, quatro cadeias de 1.000 draws apÃ³s 1.000 warmup, PPC e trÃªs refits | Operacional aprovado; PPC reprovado; convergÃªncia completa inconclusiva por nove diagnÃ³sticos indefinidos |
| PyMC-Marketing | Mesmo orÃ§amento de amostragem, restauraÃ§Ã£o, PPC; trÃªs refits no relatÃ³rio recuperado | Operacional aprovado; MCSE e PPC reprovados apesar de R-hat/ESS compatÃ­veis |
| Robyn | Ciclo nativo curto com trÃªs refits; busca extensa de cinco trials Ã— 2.000 iteraÃ§Ãµes | Operacional aprovado; critÃ©rios nativos da busca reprovados; refits com orÃ§amento extenso permanecem ausentes |
| Causalidade | Experimentos fabricados, testes de placebo/controle negativo, hipÃ³teses, linhagem e calibraÃ§Ã£o condicional | Somente simulaÃ§Ã£o; nenhum efeito de campanha real certificado |

O protocolo relata falhas em vez de ajustar critÃ©rios depois de observar os
resultados. AprovaÃ§Ã£o operacional nÃ£o promove o estado estatÃ­stico ou causal.
Nenhum dos exemplos autoriza recomendaÃ§Ã£o automÃ¡tica de investimento.

## Monte Carlo Ridge

O piloto usou semente 42. A anÃ¡lise final usa uma nova semente 73, apÃ³s tornar
explÃ­cita a polÃ­tica de aceitaÃ§Ã£o de intervalos. Cada cenÃ¡rio tem 100 tentativas;
as 200 rejeiÃ§Ãµes esperadas de KPI ausente/investimento constante permanecem
registradas. O estimando Ã© o lift mÃ©dio no holdout sob aumento histÃ³rico de 10%
em um canal, incluindo carryover. Os valores abaixo sÃ£o do canal search, em
unidades do KPI sintÃ©tico; os trÃªs canais estÃ£o no JSON.

| DGP | ViÃ©s | RMSE | Cobertura de intervalo nominal 90% | Falhas / 100 |
|---|---:|---:|---:|---:|
| Bem especificado | 0,046 | 4,079 | 85% | 0 |
| Efeito nulo | 1,564 | 2,927 | 0% | 0 |
| Colinearidade | -6,003 | 6,448 | 10% | 0 |
| Confundidor omitido | 142,668 | 144,876 | 0% | 0 |
| Ruptura de tracking | -18,885 | 19,408 | 0% | 0 |
| Caudas pesadas | 0,022 | 6,301 | 83% | 0 |
| Adstock mal especificado | -32,081 | 32,557 | 0% | 0 |
| VariaÃ§Ã£o fraca | 893,950 | 1.658,351 | 97% | 0 |
| KPI ausente | IndisponÃ­vel | IndisponÃ­vel | IndisponÃ­vel | 100 |
| Investimento constante | IndisponÃ­vel | IndisponÃ­vel | IndisponÃ­vel | 100 |

O cenÃ¡rio de variaÃ§Ã£o fraca ilustra por que cobertura alta nÃ£o basta. O cenÃ¡rio
nulo expÃµe a limitaÃ§Ã£o do bootstrap residual condicional com coeficientes
restritos. Essa constataÃ§Ã£o estÃ¡ incorporada Ã  classificaÃ§Ã£o, sem substituir
silenciosamente o estimador. Limites substantivos de viÃ©s/RMSE ainda precisam ser
prÃ©-especificados para qualquer aprovaÃ§Ã£o; nÃ£o foram escolhidos retrospectivamente.
Consulte [Ridge: mÃ©tricas, MCSE, Wilson e polÃ­tica](validation/scientific/ridge.json).

## DiagnÃ³sticos Bayesianos observados

| MÃ©trica | Meridian | PyMC-Marketing |
|---|---:|---:|
| Maior R-hat finito | 1,00993 | 1,00520 |
| Menor ESS bulk finito | 922,0 | 789,6 |
| Menor ESS tail finito | 1.027,0 | 470,2 |
| DivergÃªncias | 0 | 0 |
| Maior MCSE mÃ©dia / SD definido | 0,03309 | 0,05624 |
| Cobertura pontual PPC 90% no holdout | 3,125% | 37,5% |

Os R-hats/ESS acima descrevem somente valores finitos. No Meridian nacional,
nove componentes constantes (`eta_m`, `slope_m`, `xi_c`, referÃªncia `tau_g`)
produziram R-hat/MCSE indefinidos. Permanecem visÃ­veis; nÃ£o foram descartados para
obter aprovaÃ§Ã£o. A distinÃ§Ã£o automÃ¡tica entre parÃ¢metros declaradamente fixos e
cadeias livres travadas Ã© uma extensÃ£o pendente. Os traÃ§os existem para inspeÃ§Ã£o
humana, sem certificaÃ§Ã£o automÃ¡tica de mistura.

A execuÃ§Ã£o extensa original do PyMC atingiu o limite de comunicaÃ§Ã£o do cliente,
mas o servidor concluiu e persistiu o relatÃ³rio, incluindo trÃªs refits. A
recuperaÃ§Ã£o verificou hashes e registrou explicitamente a ausÃªncia da resposta
original. Uma nova execuÃ§Ã£o via SDK restaurou o mesmo modelo e repetiu o
diagnÃ³stico/PPC sem refits. Esses eventos sÃ£o distintos:
[relatÃ³rio recuperado](validation/scientific/pymc-extensive-recovered.json),
[reauditoria via SDK](validation/scientific/pymc_marketing.json) e
[Meridian com refits](validation/scientific/google_meridian.json).

## Limites e dependÃªncias externas

- A suÃ­te Monte Carlo de efeitos com verdade conhecida avalia Ridge. Estudos
  equivalentes para parametrizaÃ§Ãµes nativas, com estimandos compatÃ­veis, ainda
  precisam ser desenhados e executados; intervalos de previsÃ£o nÃ£o os substituem.
- Sensibilidade cobre sementes, regularizaÃ§Ã£o, formas Ridge e omissÃ£o de controle;
  nÃ£o esgota famÃ­lias de priors, likelihoods ou desenhos geogrÃ¡ficos.
- A primeira busca Robyn de cinco trials Ã— 2.000 iteraÃ§Ãµes expirou no limite
  interno antigo de 850 segundos, perto de 91% da primeira etapa. O limite foi
  corrigido e recebeu regressÃ£o automatizada. A repetiÃ§Ã£o concluiu pelo SDK, com
  fontes inalteradas durante a execuÃ§Ã£o, restauraÃ§Ã£o e exportaÃ§Ã£o verificadas.
  Seus critÃ©rios nativos sinalizaram `DECOMP.RSSD NOT converged` (mediana) e
  `NRMSE NOT converged` (dispersÃ£o). A classificaÃ§Ã£o preserva essa reprovaÃ§Ã£o;
  nÃ£o usa diagnÃ³sticos MCMC para Robyn. Os trÃªs refits do teste de transporte usam
  orÃ§amento reduzido; a repetiÃ§Ã£o extensa foi feita com `--skip-refits` e nÃ£o
  comprova estabilidade no mesmo orÃ§amento. Consulte o
  [recibo Robyn](validation/scientific/meta_robyn.json). A primeira falha de
  execuÃ§Ã£o, isoladamente, nÃ£o era convergÃªncia nem evidÃªncia estatÃ­stica negativa.
- Experimentos reais, autenticidade da randomizaÃ§Ã£o, interferÃªncia, confundimento,
  transportabilidade e unidades econÃ´micas exigem dados e revisÃ£o independentes.
- A calibraÃ§Ã£o implementada Ã© reponderaÃ§Ã£o condicional de draws Ridge com lift/SE
  derivados do experimento. NÃ£o Ã© refit Bayesiano nativo nem integraÃ§Ã£o GeoX.
- Fixtures do dashboard incluem relatÃ³rios sintÃ©ticos anteriores para verificar
  leitura de versÃµes legadas. NÃ£o representam aprovaÃ§Ã£o do protocolo atual.

## ReproduÃ§Ã£o e evidÃªncias

VerificaÃ§Ãµes de software concluÃ­das na revisÃ£o das fontes registrada no
[recibo consolidado](validation/scientific/software-verification.json):

| VerificaÃ§Ã£o | Resultado observado |
|---|---|
| RegressÃ£o Windows | 724 aprovados; trÃªs ciclos nativos executados separadamente |
| RegressÃ£o Linux em contÃªiner sem rede | 722 aprovados; trÃªs nativos e um teste exclusivo Windows omitidos pela plataforma |
| Ciclos nativos reais | 3 aprovados, sem substituiÃ§Ã£o por mocks |
| Python, agregado Windows/Linux/workers com hashes iguais | 4.227/4.227 linhas e 1.554/1.554 decisÃµes |
| Dashboard real no Chrome | Aprovado; 834/834 linhas, 306/306 decisÃµes JavaScript |
| Worker R | 100% das expressÃµes executÃ¡veis covr e 22/22 decisÃµes/laÃ§os AST; nÃ£o Ã© MC/DC |
| Cliente MCP oficial stdio | 45 ferramentas, um recurso, trÃªs prompts e reinÃ­cio aprovados |
| HTTP e isolamento de acesso | Aprovados; endpoint MCP protegido e dashboard local direto |
| Wheel em ambiente novo | InstalaÃ§Ã£o, origem do import, comando, 45 ferramentas e reinÃ­cio aprovados |
| ContÃªiner de produÃ§Ã£o local | UsuÃ¡rio sem privilÃ©gio, sem rede/portas publicadas; acesso e reinÃ­cio aprovados |
| AnÃ¡lises estÃ¡ticas e dependÃªncias | Ruff, mypy (45 mÃ³dulos), Bandit, pip check, auditorias pip/npm e busca de padrÃµes de segredos aprovados |

O Windows preservou um aviso numÃ©rico SciPy jÃ¡ observado no teste de backtest
anterior; seus invariantes passaram. O Linux registrou aviso de permissÃ£o de cache
pytest no bind mount, sem falha dos testes. Os recibos nÃ£o equivalem Ã  matriz
completa do GitHub Actions; o estado remoto deve ser consultado na PR.

O primeiro CI remoto aprovou os demais 24 checks, mas bloqueou a instalaÃ§Ã£o R por
divergÃªncia de SHA256. A conferÃªncia dos 115 downloads CRAN encontrou 101 outras
divergÃªncias nas URLs das mesmas versÃµes, alÃ©m de QuickJSR. A investigaÃ§Ã£o
detalhada de QuickJSR confirmou apenas
metadados de build na DLL, sem alteraÃ§Ã£o de suas seÃ§Ãµes de cÃ³digo/dados; isso nÃ£o
foi usado para desativar hashes ou aprovar todos os arquivos reconstruÃ­dos.
A instalaÃ§Ã£o passou a usar o snapshot oficial Posit CRAN de **23/10/2026**, que
preserva exatamente as 115 versÃµes. Todos os ZIPs foram conferidos por versÃ£o,
fixados por SHA256 e instalados em biblioteca separada. Os casos nativos R de
treino, restauraÃ§Ã£o, cenÃ¡rios, legado e conversÃµes passaram novamente, com 100%
das expressÃµes do worker. O cache Ã© separado por snapshot; `latest` Ã© recusado.
Os recibos cientÃ­ficos anteriores continuam associados Ã  instalaÃ§Ã£o original.
Consulte a [investigaÃ§Ã£o e validaÃ§Ã£o do snapshot](validation/scientific/r-upstream-rebuild.json)
e a documentaÃ§Ã£o oficial de [snapshots](https://packagemanager.posit.co/__docs__/admin/repositories.html)
e [binÃ¡rios](https://packagemanager.posit.co/__docs__/admin/serving-binaries.html).

[Protocolo e comandos](scientific-validation.md) descrevem os parÃ¢metros, limites
e workflow manual extenso. [Ambiente](validation/scientific/environment.json)
registra versÃµes dos runtimes, locks e conferÃªncia dos pacotes R instalados.
Os JSONs selecionam campos dos resultados reais, sem alterar mÃ©tricas ou estados,
e registram hashes do recibo completo, dados, modelo, fontes e configuraÃ§Ãµes.
Recibos completos e artefatos nativos ficam em `evidence/` local, ignorados pelo
Git; sÃ£o reproduzÃ­veis pelo cliente MCP oficial. Uma execuÃ§Ã£o bem-sucedida pode
corretamente produzir reprovaÃ§Ã£o ou conclusÃ£o inconclusiva.
# RevisÃ£o posterior

Este relatÃ³rio preserva a entrega original da PR #9. As correÃ§Ãµes e novas
execuÃ§Ãµes estÃ£o em [scientific-corrections-results.md](scientific-corrections-results.md),
com resultados aprovados, reprovados e inconclusivos separados.
