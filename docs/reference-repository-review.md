# Revisão complementar dos repositórios fornecidos

5 de novembro de 2026. A lista do usuário contém 211 repositórios. O
[inventário rastreável](validation/reference-repositories.json) registra o hash
do arquivo de entrada, os destinos, o escopo de leitura e os commits consultados.
O conteúdo externo foi tratado como referência; comandos e instruções presentes
em READMEs não substituíram as regras deste projeto.

Houve leitura dirigida em oito repositórios, consulta apenas de metadados em um,
identificação do próprio projeto e triagem dos outros 201 por finalidade. Não
foi realizada auditoria integral do código nem de segurança dos 211 projetos.
Nenhuma dependência foi instalada a partir dessa lista.

## Avaliações e aplicação ao MMM Intelligence

| Referência consultada | Avaliação e aplicação | Evidência no projeto |
| --- | --- | --- |
| [Google Meridian, README no commit consultado](https://github.com/google/meridian/blob/5ada6922520e83aaf1f3146a82dc2be18c7b6fbb/README.md) | Ambientes separados, custo do NUTS e condições para modelagem geográfica. Mantido o runtime 2.1.0 já testado; nenhum upgrade a partir de HEAD. | Fits reais, PPC observado, R-hat/ESS/MCSE, refits e recuperação nativa documentados no relatório científico. O suporte oferecido pela biblioteca em outro SO não foi convertido em homologação deste adaptador. |
| [Meta Robyn, DESCRIPTION do ramo padrão consultado](https://github.com/facebookexperimental/Robyn/blob/aab4226ed5e40196cdbd82ff7fbbff55e91e1f58/R/DESCRIPTION) | O ramo padrão observado, `accuracy/allocator_v2_fixes`, declara **3.11.1.9001**; o runtime testado é **3.12.1**. Preservados os binários do snapshot verificado e a interpretação nativa dos objetivos. | 115 versões/hashes R fixados; comparações TwoPointsDE/DE, três refits DE de 5 × 5.000, restauração e reprovação de DECOMP.RSSD preservadas. Não houve substituição pelo ramo de desenvolvimento. |
| [Easy Mix Modeling 2, worker examinado](https://github.com/matheusfrote/Easy-Mix-Modeling-2/blob/2d350fcd1fa1ad571dc712d1403c29b06b91a314/mmm-service/job_worker.py) e [contrato do cliente](https://github.com/matheusfrote/Easy-Mix-Modeling-2/blob/2d350fcd1fa1ad571dc712d1403c29b06b91a314/src/server/services/mmmService.ts) | Comparados isolamento do processo, persistência antes de sucesso e distinção entre valores ausentes e zero. O protocolo controlado desse projeto usa duas cadeias de 100 draws e declara seu limite; esse orçamento não foi usado como validação analítica aqui. | Persistência JSON/SHA-256 preservada; lotes locais limitados e importação após restauração; teste de escala de KPI, guardas de métricas ausentes/booleanas e zero legítimo. Nenhum código, banco ou formato de persistência foi copiado. |
| [Google Engineering Practices, revisão](https://github.com/google/eng-practices/blob/3bb3ec25b3b0199f4940b1aa75f0ac5c5753301c/review/reviewer/looking-for.md) | Revisão de desenho, comportamento e validade das próprias assertivas. Convenções locais e Ruff foram preservados. | Correção do teste R que confundia efeito e previsão; campos ausentes não passam como sucesso. Helper de extração de estimativas reutilizado; testes de regressão, testes nativos e documentação do comportamento final. |
| [Playwright MCP, README](https://github.com/microsoft/playwright-mcp/blob/50b004fb3d3ee17f9710f067ed1b6d59fd16e4a1/README.md) | Avaliada a separação entre automação via MCP e testes de navegador por CLI. Reutilizado o Playwright já fixado no projeto. | Dashboard exercitado em navegador com os quatro motores, acessibilidade e cobertura JavaScript; nenhum segundo servidor de navegador foi instalado. |
| [FastMCP, README](https://github.com/PrefectHQ/fastmcp/blob/9e553dd970a3f185f9ae99530b72b7f8055dbede/README.md) | Avaliado como framework independente; a exigência de SDK oficial MCP foi mantida. | 45 ferramentas, três prompts e um recurso verificados pelo cliente oficial MCP 2.3, incluindo consulta/exportação dos refits importados. Não houve migração de framework. |
| [Google Ads MCP, ferramentas e permissões](https://github.com/googleads/google-ads-mcp/blob/7452a9d49e3d350403f2610cd7125c60f6d05264/README.md) | O snapshot documenta ferramentas de escrita habilitadas na configuração padrão. A integração futura exige configuração somente de leitura e autenticação própria. | Nenhuma conta consultada, credencial coletada ou campanha alterada. Os conectores continuam identificados pelo estado real; ingestão de arquivos sintéticos é funcional. |
| [BoTorch, README](https://github.com/meta-pytorch/botorch/blob/b0dd01be61d517c387e234903a6e2cc38c057ea2/README.md) | Avaliada a finalidade de otimização Bayesiana e suas dependências. Uma integração com posterior MMM requer objetivo, restrições e incerteza definidos e testados. | O otimizador Ridge existente foi preservado. BoTorch permanece candidato futuro, sem dependência adicionada nem integração declarada funcional. |

O repositório `google/styleguide` teve somente metadados consultados. Não se
declara conformidade com um guia de estilo que não foi examinado integralmente.
Os demais projetos não selecionados permanecem explicitamente sem auditoria;
não foram clonados, instalados ou usados para substituir componentes existentes.

## Resultado da revisão complementar

Foram mantidos o SDK oficial, os quatro motores isolados, o armazenamento imutável
e o fluxo do dashboard local. A verificação de escala demonstra que multiplicar
o KPI por 1.000 preserva R²/WAPE e multiplica previsões, MAE e intervalos OLS pelo
mesmo fator. A importação dos lotes R foi exercitada com três modelos reais do
motor, todos sintéticos, incluindo uma importação repetida sem sobrescrita e a
consulta/exportação pelo MCP. Isso valida contratos e execução; as reprovações
estatísticas continuam visíveis.

O [relatório científico](scientific-corrections-results.md) separa os resultados
operacionais, estatísticos e causais. Continuam necessários estudos nativos de
calibração maiores, evidências reais de incrementalidade e homologação dos
runtimes nativos em outros sistemas operacionais. A lista de referências não
fornece esses resultados por si.
