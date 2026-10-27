# Resultados executados — auditoria 0.3.0

## Resultados V4 — 26/10/2026

183 testes aprovados, zero reprovados, um warning SciPy preexistente; cobertura de
linhas 1854/2273 = 81,57%. Ruff, formato, mypy, Bandit e pip check aprovados.
Quatro locks Python consultados sem vulnerabilidades conhecidas. MCP stdio/HTTP reais,
recargas Meridian/PyMC/Robyn, forecast PyMC após reinício e comparação de quatro
motores executados. Exato recusado; interseção explícita de 30 períodos.

Cobertura condicional nominal 90% em dez seeds por regime: 87,31% bem especificado,
87,31% ruído alto, 86,73% colinear, 28,08% preço omitido, 0% quebra estrutural,
86,73% ruído assimétrico. Cobertura paramétrica do canal nulo: zero. Sem certificação
causal, de posterior ou cobertura geral. [Relatório e recibos](docs/v4-delivery.md).
Resultados das versões anteriores abaixo são históricos.

Data de referência: 25/10/2026, America/Sao_Paulo. Testes reais de software sobre dados sintéticos; números abaixo não são resultados de campanhas. Evidências 0.1/0.2 preexistentes são históricas e não substituem estas execuções.

## Verificações locais

| Verificação | Resultado observado |
|---|---|
| pytest Python 3.12.14 | 105 passaram, 22,74 s |
| pytest Python 3.11.16 | 105 passaram, 22,23 s; um RuntimeWarning SciPy no solver de um fold nested, sem falha ou resultado não finito |
| SDK stdio 2.3.0 | 16 ferramentas descobertas; 13 chamadas locais, erros estruturados e persistência após reinício |
| Nativos via MCP | Três motores: geração, treino, consulta, recarga após reinício e cenário histórico ×1,1 |
| Stress | 11 casos; cinco bloqueios esperados; seis modelos × três orçamentos; zero recomendação empresarial |
| Navegador | Chrome real, visual desktop e largura efetiva 500 px; sem overflow horizontal ou recursos externos |
| Paridade de cenário | Total 26000, horizonte 8, pesos 40/30/30: Python 95344,14042879627; JS exibiu 95.344,14 |
| Dependências | pip-audit no requirements-lock.txt: zero vulnerabilidades conhecidas; não abrange advisories R nem prova segurança absoluta |

Comandos reproduzíveis (usar novas pastas para não sobrescrever evidências):

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check src tests examples server.py
.\.venv\Scripts\python.exe -m ruff format --check src tests examples server.py
.\.venv\Scripts\python.exe examples/mcp_workflow.py --extended --data-dir var/reproduce --output-dir evidence/reproduce
.\.venv\Scripts\python.exe examples/scientific_stress.py --output-dir evidence/reproduce-stress
.\.venv\Scripts\python.exe examples/http_smoke.py --output-dir evidence/reproduce-http
.\.venv\Scripts\python.exe -m build --no-isolation --outdir dist/reproduce
~~~

Os comandos nativos e instalação dos ambientes separados estão em [operações](docs/operations.md). Configuração do host é necessária; esses frameworks não são dependências do servidor base.

## Resultados estatísticos construídos

| Modelo | MAE teste | WAPE % | R² teste | Limite |
|---|---:|---:|---:|---|
| Ridge local | 98,243952 | 0,823815 | 0,976158 | Gerador da mesma família; 32 semanas |
| Baseline média treino local | 723,465912 | 6,066554 | -0,185199 | Sem futuro no cálculo da média |
| Meridian 2.1.0 | 1844,996183 | 15,471038 | -4,901421 | MCMC curto, cauda contígua, média condicional |
| PyMC-Marketing 1.3.0 | 418,136465 | 3,506243 | 0,676759 | MCMC curto, preditivo observado |
| Robyn 3.12.1 | 446,239615 | 3,734396 | 0,580638 | Um trial/200 iterações; teste nativo de 30 semanas |

Não classificar a qualidade geral dos frameworks por esta tabela: splits, transformações, baseline e semântica diferem. Ela comprova cálculos reais, inclusive resultados ruins.

Ridge: RMSE 125,041560, MAPE sem zeros 0,821439%; posto padronizado 9/9, condição padronizada 1,776584; lag1 residual -0,01633 e Durbin–Watson 1,97063, apenas descritivos. Backtests: MAE 125,500 / 131,663 / 98,244, contra baseline média 530,104 / 630,074 / 723,466. Decomposição reconcilia com erro máximo 3,64e-12. Sensibilidade: search 13,59–35,44%, social 30,28–38,43%, video 33,60–47,98%; faixas de especificação, não intervalos de confiança. [Auditoria estruturada](docs/validation/scientific-final/audit.json).

| Diagnóstico MCMC bruto | Meridian | PyMC |
|---|---:|---:|
| Cadeias / draws por cadeia / tune | 2 / 50 / 50 | 2 / 50 / 50 |
| R-hat máximo finito | 1,257068 | 1,183304 |
| ESS bulk mínimo | 6,590712 | 9,445831 |
| ESS tail mínimo | 13,589418 | 10,229867 |
| Divergências | 1 | 0 |
| R-hat indefinidos | 9 | 0 |
| Convergência certificada | Não | Não |

Prior/configuração efetiva e escopo dos diagnósticos estão em [Meridian](docs/validation/scientific-meridian.json), [PyMC](docs/validation/scientific-pymc.json) e [Robyn](docs/validation/scientific-robyn.json). Diagnóstico indefinido é contado, não omitido como sucesso. Robyn não possui R-hat/ESS MCMC. A prova R adicional conferiu o split exato em 199 comprimentos, preservação do target de validação e invariância ao target externo ×100; avisos de locale/compilação foram não fatais e não ocultados na análise.

## Evidência, publicação e escopo

`docs/validation/scientific-checks.json` agrega checks finais; `scientific-ui.json` registra a comparação do navegador. As capturas foram inspecionadas inline, sem alegar arquivo de screenshot salvo. O dashboard não mostra toda a auditoria nem intervalos completos; esses detalhes estão no JSON e neste relatório.

CI remoto, hash e push final são registrados em [IMPLEMENTATION_PROGRESS.md](IMPLEMENTATION_PROGRESS.md). A matriz base verifica nove combinações OS/Python e segurança, sem instalar os motores nativos. Nenhum deploy foi executado. Não há checker estático de tipos configurado; compileall não é typecheck. Pydantic e testes exercitam os contratos em execução. Não há aprovação de eficácia de marketing, ROI causal ou recomendação automática.
