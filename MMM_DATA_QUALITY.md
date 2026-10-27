# Dados, procedência e qualidade — 0.3.0

## Pipeline V4

import_csv/import_dataset preservam origem, unidades, tipo de KPI e autorização.
CSV original e SHA-256 são armazenados, com mapeamento, parsing de timezone, ordenação
ou agregação explicitamente solicitados. Datas duplicadas/irregulares, ausentes,
fórmulas e valores inválidos são recusados; semana parcial não é completada.
data_quality reporta lacunas, resumo/zeros, constantes, correlação, extremos 3-IQR e
mudança de nível com severidade/evidência. IQR zero é indefinido; extremos não são
removidos. Screens não provam tracking alterado nem descartam endogeneidade.

Só dados fabricados foram utilizados. Conectores são contratos offline sem APIs
ativas. [Ferramentas](docs/tools.md), [fontes](docs/connectors.md) e
[protocolo real](docs/real_data_validation.md). Registros abaixo são históricos.

**Todos os dados desta entrega são fabricados.** O usuário informou que não possui base e autorizou explicitamente dados sintéticos. Nenhum dataset empresarial foi usado; não há extração autenticada de anúncios, experimento real ou evidência de eficácia comercial. A pesquisa delimitada de exemplos oficiais identificou exemplos simulados, sem necessidade de atribuir origem real a uma base pública não comprovada.

## Base principal

| Campo | Valor |
|---|---|
| Gerador | built-in-demo-v1, seed 42 |
| Fonte | Fórmulas e ruído construídos em datasets.py |
| Período | 2023-01-02 a 2025-12-22 |
| Granularidade | 156 segundas-feiras, intervalo exato de sete dias |
| KPI | Receita sintética (`target_type=revenue`) |
| Mídias | spend_search, spend_social, spend_video |
| Controles | price_index, promotion |
| Unidade | synthetic_currency_per_period / synthetic_revenue; não é BRL ou receita contábil |
| Hash JSON canônico | 43ab06c77a76626f99ba135c46eef0b11696b53bc7fe4acb9a6d5319cef22e88 |
| Split local | 8 warmup, 116 treino, 32 teste |
| Validação | Sem ausentes, datas duplicadas ou irregularidade no exemplo base |

O CSV e os resultados estão em [scientific-final](docs/validation/scientific-final). O hash é do dataset com metadata, não do CSV. `data_context` declara DGP construído e definição do KPI. Campos empresariais como extração, moeda real, calendário e histórico de tracking não se aplicam ao gerador; são declarados ausentes, não inventados. Importações aceitam target_type e contexto explícito. Origem sintética é declaração confiada ao operador, não perícia independente.

## Verificações e stress

Validação bloqueia ausentes/não numéricos/infinitos, magnitude excessiva, target ou mídia negativos, datas inválidas/duplicadas/desordenadas, lacunas diárias/semanais e histórico abaixo do mínimo. Não imputa, remove ou ordena silenciosamente. Mídia constante no treino bloqueia modelagem por falta de variação. Outliers são sinalizados por regra descritiva de 3 IQR e permanecem nos dados; isso não identifica automaticamente tracking quebrado.

O [harness de stress](examples/scientific_stress.py), seeds 42/718, executou 11 casos: base, colinearidade, quebra de tracking na cauda, efeito de mídia nulo, KPI todo zero, mídias todas zero, target ausente, data duplicada, série irregular, histórico curto e efeito de mídia negativo. Cinco casos foram corretamente bloqueados no treino; seis produziram modelos exploratórios. Cada modelo foi submetido a 0,5×/1×/2× orçamento de referência: conservação de total verificada e zero recomendações de verba comercial. [Evidência](docs/validation/scientific-stress.json).

O caso negativo viola a hipótese de mídia não negativa e não deve ser interpretado como efeito recuperado. O caso sem efeito mostra que associação ou coeficiente positivo não demonstra incrementalidade. Colinearidade pode impedir separação por canal mesmo com bom ajuste agregado. Zeros do KPI deixam R²/WAPE indefinidos conforme o denominador; MAPE exclui zeros e informa sua contagem.

## Limites para dados empresariais

Antes de uso real: autorização do operador e do host, definições de KPI/moeda/período, completude das fontes, calendário, promoções, preço, distribuição, concorrência, mudanças de tracking e controles escolhidos com fundamento causal. Não declarar controle endógeno como correção de confundimento. História de adstock anterior à primeira linha é desconhecida. Gasto é proxy de exposição e não corrige leilão ou seleção de audiência.

A suficiência temporal mínima do software não equivale a suficiência estatística. Não há validação experimental, cobertura empírica de intervalos em negócios, sensibilidade contextual de priors ou transporte de lift. A validação com dados reais permanece bloqueada pela ausência de base e não impede concluir a entrega funcional sintética autorizada.
