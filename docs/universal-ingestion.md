# Ingestão fornecida pelo usuário e ciclo de Growth

Implementação incremental de 29/10/2026. A base anterior tinha 198 testes e 26
ferramentas. A extensão inicial acrescentou 13 ferramentas; o fechamento acrescenta
outras seis, totalizando 45. Preserva as entradas das
anteriores. Nenhuma API de plataforma de mídia é chamada.

## Arquitetura e uso

`universal_schemas` define contratos limitados; `supplied_files` lê conteúdo de
arquivos; `media_validation` implementa perfis e screens descritivos; `growth`
orquestra autorização, procedência e snapshots. A fronteira continua sendo o serviço
existente e o SDK MCP oficial. Ferramentas recebem `{"request": {...}}` e retornam
`ToolResponse`; verifique `ok` antes de consumir `data`.

O cliente lê um arquivo autorizado e envia seus bytes em `content_base64`. O servidor
não recebe caminhos, URLs, SQL, conexões ou credenciais. Uma exportação tabular de
banco pode usar os mesmos formatos. Dados reais exigem a permissão do host
`MMM_ALLOW_REAL_DATA=true` e referência de autorização; declarar a referência
isoladamente não concede permissão. O cliente deve revisar dados pessoais antes de
enviar, visualizar ou exportar conteúdo. Não há anonimização automática.

| Ferramenta | Entrada/resultado principal |
|---|---|
| preview_dataset | content_base64, format, origin, synthetic, encoding, delimiter, header_row, sheet; prévia de até dez linhas, schema físico, contagem, abas e hash; sem persistência |
| import_source | Mesma entrada e confirm=true; persiste bytes originais em base64, schema, parsing e procedência |
| list_media_profiles | Perfis iniciais e instrução para criar perfis personalizados |
| register_media_profile | name, version, family, required, optional, expected_units, nonadditive; retorna ID de definição imutável |
| map_dataset_schema | source_id, profile (nome inicial ou ID customizado), mapping origem→campo lógico, units, dimensions, date_format, timezone, frequency_days; cria versão normalizada |
| validate_media_dataset | artifact_id normalizado; erros, avisos, ausência aplicável/não aplicável, completude, duplicidade, lacunas e alcance do screen |
| validate_crossmedia_dataset | artifact_ids normalizados; matriz, períodos comuns, diferenças de unidade/metodologia/universo/região/frequência |
| build_growth_dataset | artifact_ids, frequency daily/weekly e aggregations por métrica; observações canônicas com fonte, dimensões e unidades preservadas |
| check_mmm_eligibility | artifact_id normalizado, kpi, media, controls, backend; bloqueios de desenho, sem inferência causal |
| create_growth_diagnostic | artifact_id normalizado; evidências descritivas de primeira/última observação, qualidade, hipóteses alternativas, abstenção e próxima investigação |
| create_growth_decision | diagnostic_id, problem, hypothesis, action, kpi, guardrails, baseline, horizon, method, risks; proposta sem execução externa |
| transition_growth_decision | artifact_id, state, actor, note, plan/results_id conforme a etapa; novo snapshot imutável |
| get_growth_artifact | artifact_id; recupera fonte, perfil, normalização, Growth, diagnóstico ou snapshot autorizado |
| join_datasets | left_id, right_id, keys, cardinality, how, aggregations, frequency, context, confirm; prévia antes de novo artefato |
| prepare_mmm_dataset | artifact_id, backend, kpi, media, controls, target_type, currency; dataset imutável e chamada validada de treino |
| analyze_growth | artifact_id, metrics, group_by, rolling_window, lag_pairs, max_lag; tendências e mudanças de nível descritivas |
| analyze_cohorts | fonte de eventos, unit_column, event_column, entry_event, return_event, as_of, horizon; denominadores com acompanhamento completo |
| plan_experiment | desenho, desfecho, baseline, MDE, variância quando contínuo, alpha, power, população, janela e proteções; plano/poder aproximado |
| analyze_experiment | artifact_id de fonte e plan_id; estimativa, intervalo, SRM, perdas, guardrails e custo descritivo quando configurados |

## Formatos e interpretação

CSV, TSV/outro delimitador explícito, JSON (array de objetos), JSONL/NDJSON, XLSX,
XLS BIFF, Parquet de arquivo único e XML tabular de seletores explícitos.
`format="jsonl"` também atende NDJSON. Encoding: UTF-8/UTF-8 com BOM, CP1252 ou Latin-1.
Cabeçalhos tabulares são explícitos, únicos e não vazios. Linhas JSON devem ter o
mesmo schema; use `null` para valores desconhecidos. Células aninhadas são recusadas.
Não há inferência de significado a partir de nomes de campanhas ou colunas.

XLSX requer `python -m pip install ".[files]"`. Use `sheet` quando houver mais de
uma aba. Fórmulas, macros, vínculos externos, arquivos ZIP inválidos, entradas de
travessia e volume expandido excessivo são recusados. Leitura somente consulta,
com limites de linhas/colunas durante a iteração. Proteção XML exige defusedxml,
conforme a [documentação oficial](https://openpyxl.readthedocs.io/en/stable/).
O modo de leitura e fechamento segue
[read-only workbooks](https://openpyxl.readthedocs.io/en/stable/optimized.html).

XLS verifica assinatura OLE/BIFF, seleciona abas e lê tipos/datas; macros não são
executadas. Fórmulas podem conter apenas resultados em cache, cuja atualidade não
é garantida. Parquet aceita tipos escalares, desativa extensões e arquivos externos,
limita metadados e bytes expandidos/decodificados em lotes antes de converter linhas.
XML requer `xml_record` e `xml_fields`, com caminhos de filhos e atributo terminal;
recusa hierarquias ambíguas, XPath arbitrário, DTD, entidades externas e profundidade
excessiva. `xml_schema_base64` valida um XSD local de até 64 KiB com lxml, no subconjunto
estrutural/tipos/limites/enumeration. Import/include/ref, regex, XPath e extensões
de schema são recusados. Não promete XML semântico universal. Referência:
[validação oficial lxml](https://lxml.de/validation.html).

XLS e XLSX preservam horários até o mapeamento explícito: meia-noite pode representar
uma data; `2026-01-05T12:30:00` permanece um timestamp e exige conversão declarada.
Parquet aninhado/binário não suportado retorna `FILE_INVALID`; nomes duplicados
retornam `SCHEMA_INVALID`. O original e seus metadados permanecem nos bytes imutáveis.
Seletores XML absolutos como `/root/record/nested/value` e `/root/record/@id`
são aceitos somente dentro da ancestralidade do registro atual; `/root/metadata`
não pode fornecer valores a outro registro. Caminhos relativos continuam disponíveis.

Original, normalização, dataset Growth, diagnóstico e decisão são artefatos
separados sob `reports`, com `artifact_type`, ID, data de criação, envelope SHA-256
e referências. O conteúdo original nunca é reescrito. Novo mapeamento gera novo ID.
Perfis personalizados também são imutáveis; selecione a versão pelo ID retornado.
Inventário/retenção existentes preservam referências e impedem exclusão de fonte
referenciada pela CLI. Os limites atuais de artefato também abrangem base64/JSON;
um arquivo próximo do limite de bytes pode exceder o limite do envelope persistido.

## Perfis e metodologia

Perfis: TV, rádio, impressos, website, SEO, Search Ads, YouTube orgânico/pago,
TikTok orgânico/pago, Kwai orgânico/pago, Facebook e Instagram orgânico/impulsionado/Ads.
Canal, plataforma/veículo, estratégia, campanha, região, segmento e formato são
dimensões distintas. A declaração de canal é explícita; a origem não é autenticada
pelo nome. Perfil personalizado permite outro canal sem alteração de código.

Os conjuntos opcionais diferem por meio. Audiência tradicional exige revisão de
universo, metodologia, praça e período. Valores ausentes continuam `null`; zero é
um valor observado. CTR usa fração; CPC/CPA usam numerador/denominador declarados.
Unidades não identificadas geram aviso; unidades incompatíveis com regras do perfil
geram erro. Datas inválidas, grão duplicado e números inválidos são diagnosticados.

Agregação exige regra por métrica. `sum` é bloqueado para alcance, usuários únicos
e outras métricas declaradas não aditivas no perfil. `ratio` exige dois campos em
`ratios`; `weighted_mean` exige campo de peso em `weights`. Ausência é propagada,
sem imputação. A média ponderada continua uma estatística da métrica fornecida;
não cria alcance deduplicado. Nenhuma soma crossmedia de audiência é produzida.
O dataset canônico mantém observações por fonte/grão e não faz joins automáticos.

Elegibilidade MMM é um screen preliminar sobre normalização: ao menos 52 datas
únicas, uma observação por data, regularidade, números completos, unidades,
variabilidade, correlação entre mídias, controles e definição do KPI. O destino é
explícito: Meridian exige receita, Robyn exige declaração revenue/non_revenue; a
materialização valida também os contratos reais dos adaptadores antes de gravar o
dataset. As interfaces atuais usam gasto como proxy de exposição, não fabricam
geografias, população ou alcance. Aprovação no screen não garante desenho adequado, convergência ou
identificação causal. Growth pode ser descritivamente utilizável e continuar
inelegível para MMM. Os motores e importações anteriores permanecem disponíveis.

## Decisão e aprendizado

Transições: `proposed → approved → planned → evaluated → learned`; rejeição é
permitida a partir de proposed/approved. `planned` exige hipótese falsificável,
unidade, janela, duração, premissas amostrais, controle, guardrails, sucesso e parada.
Método distingue randomized, observational, before_after e mmm_calibration.
`evaluated` exige um artefato de resultados importado e autorizado.

O parecer é registrado em `note`. O plano estatístico fornece amostra aproximada
para unidades independentes, com mínimo de cinco por braço; não garante poder de
Fisher/Welch. A análise binária usa diferença de proporções, IC Newcombe/Wilson e
Fisher exato; contínua usa Welch. O ajuste de Bonferroni cobre KPI e guardrails
especificados. Guardrails exigem desfecho, direção adversa e limite; sem especificação
não são avaliados. CPA é razão de totais entre casos completos, sem IC; zero conversões
produz indisponibilidade. População e janela são verificadas apenas quando colunas,
valor elegível e datas são declarados; texto livre não comprova compatibilidade.
Unidades repetidas são recusadas: pareamento/medidas repetidas ainda não têm estimador.
Não é estimador causal para dados observacionais. Resultados sintéticos permanecem identificados.
O plano de decisão pode apontar `experiment_plan_id`; nesse caso `evaluated` exige
a análise estatística daquele plano e KPI, preservando o vínculo no histórico.
Plano e resultados só podem ser fornecidos nas etapas correspondentes. O ID da
próxima revisão é determinístico; duas tentativas de ramificar o mesmo snapshot
colidem em vez de sobrescrever histórico. Revisões de hipótese podem ser registradas
como nova proposta ligada ao diagnóstico. `actor` é uma declaração de revisão
humana, sem comprovação de identidade. Não há execução de campanhas, ajustes
automáticos do modelo ou envio de evidências à calibração.

## Demonstração e verificação

Evidência histórica da primeira extensão (não representa o fechamento atual):
**230 testes aprovados**, cobertura **82,41%**, um aviso SciPy
preexistente. Ruff/formatação, mypy em 36 módulos, Bandit, pip check e scanner de
padrões de segredos passaram. E2E Chrome do dashboard anterior passou com a nova
descoberta de ferramentas. Revisão independente confirmou os cinco achados
corrigidos e executou separadamente os 32 testes da extensão.

A demonstração executou 38 chamadas em sete fontes sintéticas, descobriu 39
ferramentas e confirmou igualdade do snapshot após reinício.
[Recibo MCP](validation/growth/mcp-demo.json) e
[relatório sintético](validation/growth/report.md). Esses resultados são locais;
nenhum novo CI remoto ou comportamento de API de anúncios foi certificado.
O [wheel instalado](validation/growth/wheel.json) também passou em venv limpa,
com origem da importação verificada, 39 ferramentas e ciclo MCP anterior de 23
chamadas/recarga. O pacote continua na versão 0.4.0 local, sem release nova.

```
python examples/growth_workflow.py --output-dir evidence/minha-demo-growth
python -m pytest -q
```

Use diretório de saída novo. A demonstração gera arquivos sintéticos de sete meios,
envia conteúdo pelo MCP, produz matriz/canônico/screen/diagnóstico, registra proposta,
revisão/plano/resultados/aprendizado, reinicia o servidor e compara o snapshot.
Os arquivos result.json e report.md ficam nessa pasta, sem uploads.

Desenvolvimento: skill superpowers:test-driven-development (RED/GREEN), testes
locais Python/SDK MCP e revisão independente por agente somente leitura. GitHub e
plataformas de Marketing não foram utilizados para coletar dados. As duas páginas
oficiais openpyxl acima foram consultadas via ferramenta web para leitura e segurança
XML. Nenhuma nova validação empresarial ou dos motores nativos é alegada.

Estado atual, resultados das novas execuções e pendências de cobertura/testes:
[checklist de fechamento](closure-checklist.md). O CI exige 100% e ainda não tem
evidência de aprovação desse critério. Nenhum push ou deploy desta extensão foi feito.
