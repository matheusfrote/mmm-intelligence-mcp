# Revisão para integração à main

Data: 5 de novembro de 2026. Escopo: PR #9 (validação científica), PR #10
(correções científicas) e revisão adicional sobre `f8ea402`.

## Achados e correções

A identidade dos refits Robyn considerava o worker R, mas omitia o wrapper
Python `integrations/worker.py`. Esse wrapper valida o tipo de alvo, prepara
metadados e serializa o resultado. Uma alteração nele podia manter a identidade
do modelo e permitir a reutilização de um ajuste gerado pelo código anterior.

O wrapper agora participa de `source_sha256` ao lado de `robyn_worker.R`.
O teste de regressão altera apenas os bytes observados pelo cálculo de hash,
sem executar um motor fictício: antes da correção a identidade permanecia igual
e o teste falhava; depois, a identidade muda. Os 13 testes relacionados a refits,
biblioteca R e admissão dos lotes passaram.

Não há migração silenciosa de resultados antigos. Artefatos históricos continuam
consultáveis e restauráveis, mas não são reidentificados como ajustes executados
sob a nova política. Um refit ou lote antigo sem a identidade completa não deve
ser anunciado como uma nova execução reutilizável. Essa correção não altera
estimativas, priors, critérios de aprovação ou as evidências científicas já
registradas.

A revisão adicional identificou uma aprovação possível na avaliação Monte Carlo
com intervalos ausentes: 1.000 ajustes bem-sucedidos, mas somente 500 intervalos
com cobertura de 100%, podiam passar pelo classificador. A cobertura calculada
apenas no subconjunto disponível não justifica uma conclusão para todos os
ajustes; a disponibilidade pode depender do posto ou da alavancagem.

Agora, qualquer intervalo ausente entre os ajustes bem-sucedidos dos cenários
centrais impede aprovação. O motivo é registrado como
`incomplete_interval_availability`; subcobertura e outras falhas continuam tendo
precedência sobre o estado inconclusivo. Denominadores ausentes também impedem
aprovação, sem presumir disponibilidade completa. A saída preserva os dois denominadores
e declara a política. Os dois casos de regressão falharam antes da correção e
passaram depois; os 23 testes de Monte Carlo e recuperação também passaram.
Os números 1.000/500 são uma fixture explícita do classificador, não um estudo
executado nem evidência de funcionamento nativo.

Uma [reavaliação dos seis agregados publicados](validation/premerge-interval-reassessment.json)
registra os hashes das entradas e o novo screen de cobertura. Nenhuma amostragem
foi repetida ou inventada. Os screens permanecem inconclusivos; as reprovações
MCMC/busca dos relatórios completos continuam valendo independentemente desse
screen. A política não altera os níveis nominais ou limites de precisão.
Os hashes dessa reavaliação usam os bytes dos blobs do Git na revisão registrada,
sem depender da conversão de quebras de linha no checkout Windows. Os seis hashes
de entrada e o hash do classificador foram reconferidos contra os blobs publicados.

## Escopo da revisão

Foram revisados os caminhos alterados de inferência Ridge, diagnósticos e
persistência nativos, identidade/reutilização de refits, importação de lotes,
experimentos pareados e por clusters, classificação científica e exportação.
A revisão independente encontrou os dois problemas acima; não houve cópia de
código de terceiros nem substituição de resultados nativos por mocks.

A revisão das fronteiras operacionais incluiu armazenamento JSON imutável com
SHA-256, bloqueio de caminhos externos, autenticação e isolamento do MCP HTTP,
acesso direto restrito ao dashboard de loopback, subprocessos com limites,
dependências fixadas e workflows de qualidade. A revisão de referências externas
permanece documentada em [reference-repository-review.md](reference-repository-review.md).

## Verificações locais desta revisão

| Verificação | Resultado / escopo |
| --- | --- |
| Suíte Python principal com cobertura habilitada | 811 aprovados, 9 casos opcionais separados, zero falhas |
| Suíte focada nos workers nativos e contratos de baseline | 12 aprovados, zero falhas, um caso de dependência exclusiva ignorado no host e exercitado no runtime Meridian; há casos compartilhados com a suíte principal |
| Ruff, formatação, mypy e Bandit | Aprovados; 49 módulos analisados pelo mypy, zero achados Bandit |
| Pacote wheel instalado fora do checkout | 45 ferramentas descobertas, 23 chamadas locais e persistência após reinício verificadas |
| SDK MCP oficial por STDIO, fluxo sem amostragem nativa | 42 ferramentas executadas, três prompts, um recurso, oito formatos e 18 perfis; as três ferramentas nativas são verificadas em ciclos separados |
| Dashboard no Chromium | Fluxo sintético real sem login aprovado; 837/837 linhas, 308/308 ramos e 217/217 funções JavaScript |
| Segurança HTTP real em loopback | Sem token: 401; leitor sem escrita; isolamento por usuário; expiração, revogação, Host/Origin, limites e cabeçalhos verificados |
| Estresse científico | 11 cenários sintéticos; zero recomendações comerciais autorizadas |
| Protocolo científico público atualizado | Execução e exportação por STDIO aprovadas; classificação estatística inconclusiva e causal `simulation_only` preservadas |
| Dependências | `pip check` sem conflitos; `pip-audit` dos quatro locks Python e `npm audit` sem vulnerabilidades conhecidas na consulta desta revisão; sem certificação de segurança de todos os pacotes R |
| Segredos | Zero achados dos padrões reconhecidos no checkout e no histórico Git local; não equivale a garantia universal de ausência |
| Opções NUTS Meridian | Assertivas executadas no runtime isolado, incluindo o alvo de aceitação padrão e explícito |

A suíte principal emitiu um aviso numérico interno do SciPy no teste de seleção
temporal aninhada. O teste passou, e o solver continua exigindo sucesso e
coeficientes finitos; o aviso não foi ocultado nem convertido em evidência de
convergência estatística.

Os caminhos locais de evidência desta rodada são `var/premerge-*.log`,
`evidence/premerge-operational/`, `evidence/premerge-http/` e
`evidence/premerge-scientific-stress/`. Eles contêm apenas testes sintéticos e
continuam ignorados pelo Git. Os workflows reproduzem os testes publicamente;
o merge deve aguardar os checks do head atualizado da PR #10, incluindo o gate exato de
cobertura Python e os ciclos nativos, sem aproveitar cobertura de código com
hash diferente. O fluxo nativo do CI executa as 45 ferramentas pelo SDK oficial,
além dos testes de ajuste/restauração e dos gates de cobertura R.

A PR #10 foi direcionada à `main` para integrar também os commits da PR #9 que
já estão em sua ancestralidade. Isso preserva o histórico e permite verificar
o conjunto final antes de uma única integração, sem reescrever a branch principal.

## Limites que permanecem explícitos

O [relatório científico](scientific-corrections-results.md) continua sendo a
fonte das métricas antes/depois e das evidências nativas extensas. A aprovação
operacional não muda as reprovações de sensibilidade do Meridian, a precisão
limítrofe em dados independentes do PyMC ou a reprovação de DECOMP.RSSD nos
refits Robyn. Cenários adversos de Ridge também continuam reprovados ou sem
intervalos identificáveis quando apropriado.

Não é defensável garantir correção estatística universal ou causalidade a partir
de testes de software e dados fabricados. Permanecem necessários estudos nativos
maiores de calibração, experimentos reais de incrementalidade e homologação dos
adaptadores nativos em Linux/macOS. A matriz de CI do pacote principal nesses
sistemas não substitui essa homologação. Nenhuma campanha, orçamento real ou
serviço externo é alterado por esta entrega.
