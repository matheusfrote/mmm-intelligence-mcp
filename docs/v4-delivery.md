# Entrega V4 — 26–27/10/2026

Versão de código 0.4.0 preparada na branch local `feat/v4-intelligence`, partindo de
`015eaeff6e6606bdaac70ff66c3ea4fe193660b1`. **Sem commit, push, merge, tag, release, PyPI
ou deploy nesta etapa.** Apache-2.0 foi autorizada pelo proprietário e aplicada.
As decisões anteriores de usar somente dados fabricados, manter somente GitHub como
destino eventual e encerrar Strix foram preservadas. Não houve alteração de campanhas.

## Diagnóstico e estado final

A inspeção encontrou 0.3.1 funcional, 16 ferramentas, 131 testes aprovados e 82,35% de
cobertura de linhas. Main local/remota eram iguais e a árvore estava limpa. Consulta
read-only confirmou main sem proteção, nenhuma tag/release e nome sem publicação PyPI.
O inventário inicial e suas vinte pendências estão na [matriz V4](v4-matrix.md).
Nenhum componente funcional foi substituído por mock ou fallback com rótulo nativo.

Agora há **26 ferramentas**, mantendo os contratos anteriores e adicionando ingestão
CSV, qualidade, análise/comparação canônica, capacidades, projeção por período,
exportação, inventário, retenção e estado das fontes. Fonte, testes, exemplos e docs
estão preparados para revisão. Os [arquivos alterados](validation/v4/changed-files.txt)
e o diff contra o commit base identificam esta entrega; novos arquivos ainda não
versionados também fazem parte do conjunto.

| Dimensão | Evidência e limite |
|---|---|
| Prontidão técnica | 183 testes aprovados, descoberta/23 chamadas/reinício MCP, HTTP real, três recargas nativas, PyMC futuro e painel no Chrome |
| Prontidão operacional | Local stdio/loopback, CLI, empacotamento e controles do host; sem SaaS público, fila durável, identidade corporativa ou quotas globais |
| Validade científica | Experimentos sintéticos e métodos inspecionados; diagnósticos bayesianos curtos inadequados, cobertura não certificada e nenhuma evidência causal empresarial |

## Problemas encontrados e corrigidos

- Faltavam licença e metadados de distribuição: Apache-2.0/NOTICE e testes de conteúdo
  dos archives foram adicionados. Governança, templates e Dependabot preparados.
- CSV não era ferramenta: agora há parsing limitado, mapeamento, timezone, decimais,
  políticas explícitas de ordenação/duplicidade/agregação e original com hash.
- Não havia comparação executável com datas/KPI verificados: contrato canônico recusa
  incompatibilidade; interseção alinha métricas e intervalos. Datas iguais não recebem
  uma certificação de protocolo justo.
- Faltava futuro nativo: PyMC restaura posterior, inclui mídia/controles intermediários
  e projeta depois da última observação. Não reusa target de holdout para reajuste.
- Diagnósticos não tinham classificação explicável: quatro estados distinguem
  falha, insuficiência e adequação apenas aos screens avaliados.
- O estudo encontrou falha de cobertura para coeficiente nulo na fronteira: a saída
  passou a advertir explicitamente e recusar interpretação como teste de efeito nulo.
  Os intervalos não foram alterados artificialmente para melhorar a cobertura.
- Inventário/retenção estavam ausentes: plano não destrutivo e exclusão CLI unitária
  verificam hash e referências. Corrigido o CLI para honrar o limite de arquivo do host.
- Três anotações de tipos e alinhamento de arrays foram corrigidos após testes RED.
  Nenhum teste anterior foi removido.

## Testes e evidências

| Verificação executada | Resultado |
|---|---|
| pytest completo, Windows/Python 3.12.14 | **183 aprovados, 0 reprovados**, 35,17 s, um RuntimeWarning SciPy preexistente |
| Cobertura de linhas | **1854/2273 = 81,57%**; baseline 1297/1575 = 82,35%; mínimo CI 80% |
| Ruff lint / format | Aprovados; 65 arquivos Python formatados |
| mypy | Aprovado nos 31 módulos de fonte |
| Bandit / pip check | Sem problemas reportados / sem requisitos quebrados |
| pip-audit | Sem vulnerabilidades conhecidas nos locks base 76, Meridian 75, PyMC 55 e Python Robyn 17; nenhum pacote ignorado |
| Stdio oficial SDK 2.3 | 26 ferramentas descobertas, 23 chamadas locais, erros negativos e persistência após reinício |
| HTTP loopback real | 401, isolamento, reader, expiração, bloqueio, Host/Origin, 413 e 429 verificados |
| Native reload | Meridian, PyMC e Robyn reais, previsões conferidas com saídas persistidas |
| Futuro PyMC | Quatro períodos posteriores ao histórico, recarga e repetição após novo processo |
| Comparação de quatro motores | Mesmo hash; modo exato recusado; interseção explícita de 30 períodos; sem vencedor |
| Stress científico | Onze regimes, recusas esperadas, nenhuma recomendação empresarial |
| Recuperação/cobertura | Sessenta ajustes, seis regimes, dez seeds, 100 bootstraps por ajuste |
| Chrome/painel | Navegação, seis polylines, CSV/JSON, entrada inválida, CSP e paridade Python/JS; sem overflow em 500 e 1440 px |
| Wheel/sdist | Conteúdo/licença/privacidade testados; instalação limpa fora do checkout aprovada, 26 ferramentas/23 chamadas/reinício |

Detalhes: [checks](validation/v4/checks.json), [ciclo MCP](validation/v4/mcp-cycle.json),
[HTTP](validation/v4/http.json), [auditoria de dependências](validation/v4/dependency-audit.json),
[UI](validation/v4/ui.json), [instalação limpa](validation/v4/wheel-install.json) e
[índice das evidências](validation/v4/README.md). Scanner de padrões de segredos cobre
worktree e história Git local; seu recibo está no índice, sem valores sensíveis.

Cobertura não instrumenta os subprocessos CLI/nativos; essas execuções são verificadas
separadamente. Não foram excluídos módulos para aumentar o percentual. O aviso SciPy
ocorre no backtest nested já existente, com resultados verificados finitos e testes
aprovados; não foi escondido. Pip-audit não audita R/binários do SO nem garante ausência
de vulnerabilidades desconhecidas. Não foi repetido o treino MCMC pesado dos modelos
históricos: os novos caminhos restauraram artefatos sintéticos já ajustados.

## Resultados científicos e motores

O experimento controlado usa coeficientes 3000/1800/0, adstock 0,5, Hill de expoente 1,
controle de preço negativo, tendência e sazonalidade. Formas são correspondentes por
construção; não se afirma recuperação irrestrita de transformações.

| Regime | Cobertura média condicional, nominal 90% | MAE médio de holdout |
|---|---:|---:|
| Bem especificado | 87,31% | 40,04 |
| Ruído alto | 87,31% | 400,45 |
| Colinearidade | 86,73% | 39,77 |
| Preço omitido | 28,08% | 91,42 |
| Quebra estrutural | 0,00% | 2594,83 |
| Ruído assimétrico | 86,73% | 189,13 |

Os números são sintéticos. Dez replicações não certificam cobertura. O coeficiente
nulo teve cobertura percentil zero; colinearidade produziu boa previsão e recuperação
ruim de coeficientes separados. Esses resultados impedem interpretar baixo erro como
atribuição válida. A [metodologia](methodology.md) explica fronteira, dependência temporal,
incerteza condicional e limitações. [Estudo](validation/v4/recovery.json).

| Motor | Estado técnico | Limite científico/funcional |
|---|---|---|
| Ridge | Treino, tuning temporal, backtesting, projeção, otimização e calibração aproximada funcionais | Não bayesiano; formas fixas/selecionadas; bootstrap não testa efeito nulo; nenhuma causalidade demonstrada |
| PyMC-Marketing 1.3.0 | Adapter real; NetCDF recarregado; futuro/reinício reproduzíveis | MCMC curto classificado inadequado; sem otimização nativa, estudo amplo de priors/PPC/mistura |
| Meridian 2.1.0 | Adapter real; Protobuf recarregado e análise canônica verificada | Diagnósticos inadequados, incluindo divergências; futuro e otimização não implementados nesta API |
| Robyn 3.12.1 / R 4.5.2 | Recarga JSON real e resposta histórica; comparação respeita split próprio | Busca curta não certifica estabilidade; sem futuro/otimização nativa expostos; não é MCMC |

R-hat/ESS configuráveis são screens, não certificação. Dados/causalidade, variáveis
omitidas, sensibilidade de priors e transporte de experimentos exigem estudo adicional.
O mecanismo mantém a mensagem: **“Não há evidência suficiente para sustentar uma
recomendação de investimento confiável com os dados e as condições atuais.”**

## Funcionalidades parciais e pendências

Conectores: dez contratos declarados e reconciliação offline testada. Adapters API,
OAuth, coleta, retries, sincronização e reconciliação de conta real **não implementados**.
É necessário código adicional e fonte autorizada. [Documentação](connectors.md).

Projeção: Ridge/PyMC funcionais; Meridian/Robyn retornam indisponibilidade explícita.
Otimização continua Ridge com total/mínimos/máximos, candidato matemático e
recommended_spend=null; nenhum otimizador externo foi apresentado como pronto.
Dashboard: [HTML local](validation/v4/dashboard.html) com qualidade, resíduos,
componentes reconciliados, curvas estacionárias, simulação e exportação. Não é uma
aplicação de treinamento/comparação multimotor; não há botões de fluxo fictício.

Distribuição: wheel/sdist locais, CLI e licença aplicados; pipx/uvx documentados sem
execução independente. Nenhuma release/tag/PyPI criada. Matriz CI existente preservada
com cobertura e wheel limpo; workflows manuais PyMC/Meridian/distribuição preparados.
**Nenhum job V4 remoto rodou.** Robyn ainda não tem provisionamento CI R. Os nove jobs
históricos aprovados em 0.3.1 não são reutilizados como prova de V4.

Segurança/operação: reader/tenant, limites, links, integridade, logs, imutabilidade e
workers preservados. Não há exclusão MCP, fila durável, quota total de disco ou proteção
contra administrador local hostil. CLI de exclusão exige servidor parado, hash exato
e revisão dos dependentes; backups não desaparecem com o arquivo. HTTP estático local
não é identidade corporativa. Arquitetura futura em [architecture.md](architecture.md).

## Bloqueios, autorizações e próximos passos

Dados reais/experimento: [protocolo empresarial](real_data_validation.md); não há base
do usuário nem eficácia de negócio certificada. Autenticação: contas de origem e
cofre para adapters, PyPI para publicação. Autorização externa: push/PR quando solicitado,
release, PyPI, regras de proteção da main e qualquer implantação exigem escopo próprio.
A autorização Apache foi consumada; não precisa ser solicitada novamente.

Mudanças estão preparadas para revisão, sem commit/push novo. Os conjuntos são
governança/CLI, ciência/dados/contratos, projeção/painel/lifecycle e testes/docs/CI.
Preservar os arquivos novos ao preparar commits. Após publicação autorizada, executar
o CI V4 do commit exato e revisar os jobs nativos separadamente. Depois, priorizar
adapters de KPI/Google/Meta, validação real e incerteza na fronteira. Pendências futuras
e critérios estão no [roadmap](roadmap.md), sem porcentagem arbitrária de conclusão.

## Recursos usados e referências

Skills locais de test-driven-development e security-and-hardening orientaram RED/GREEN,
testes negativos e preservação do escopo. GitHub MCP consultou o repositório; Chrome
DevTools MCP verificou o HTML real. SDK MCP executou os fluxos de cliente/servidor.
Não foram usados Strix nem plataformas de anúncios. Referências oficiais consultadas:
[MCP](https://py.sdk.modelcontextprotocol.io/),
[Meridian holdout](https://developers.google.com/meridian/docs/advanced-modeling/holdout-observations),
[Meridian health checks](https://developers.google.com/meridian/docs/post-modeling/health-checks),
[PyMC posterior predictive](https://www.pymc-marketing.io/en/latest/api/generated/classmethods/pymc_marketing.mmm.mmm.MMM.sample_posterior_predictive.html),
[Robyn](https://facebookexperimental.github.io/Robyn/docs/features/),
[Stan diagnostics](https://mc-stan.org/learn-stan/diagnostics-warnings.html),
[SciPy lsq_linear](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.lsq_linear.html),
[NumPy quantile](https://numpy.org/doc/stable/reference/generated/numpy.quantile.html).
Foram inspecionadas também as implementações instaladas nos caminhos alterados.

Fechamento em 27/10: corrigida inclusão do CSV/txt de evidências no sdist, verificada
por teste de distribuição. A primeira instalação foi impedida por ACL do arquivo
wheel criado pelo usuário isolado do sandbox; apenas o arquivo distribuível recebeu
as permissões herdadas de sua pasta. A repetição instalou a versão 0.4.0 em venv nova,
fora do checkout, com importação do wheel confirmada e ciclo MCP completo aprovado.
