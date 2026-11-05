# Validação científica do MMM Intelligence

A camada é aditiva ao servidor existente. `audit_model` sem `scientific` mantém
a auditoria Ridge anterior. O modo científico atende os quatro motores e salva
um relatório separado, imutável, com hashes do modelo e do dataset. Nenhum ajuste
original é sobrescrito e nenhuma campanha ou alocação real é alterada.

## Três avaliações independentes

| Dimensão | O que a avaliação pode estabelecer | O que não estabelece |
|---|---|---|
| Operacional | Linhagem do dataset e sucesso do solver ou restauração nativa | Adequação estatística, segurança universal ou identificação causal |
| Estatística | Atendimento aos critérios medidos do protocolo e resultados adversos | Verdade do modelo, convergência matemática garantida ou validade empresarial |
| Causal | Força e limitações das evidências declaradas e testes de falsificação | Autenticidade da randomização ou ausência comprovada de confundimento |

`passed_for_protocol` significa somente atendimento ao escopo numérico declarado.
`failed` preserva diagnósticos reprovados; `inconclusive` preserva evidência ausente,
insuficiente ou não conclusiva. Em dados sintéticos a avaliação causal permanece
`simulation_only`, mesmo quando os demais critérios passam. O nível mais forte
de evidência experimental continua pendente de revisão externa; declarações não
autenticam um desenho causal. `business_recommendation_eligible` continua falso.

## Meridian e PyMC-Marketing

O worker restaura o formato nativo e calcula estatísticas com ArviZ instalado no
runtime correspondente: R-hat normalizado por ranks e dividido, ESS bulk/tail,
MCSE da média/SD e divergências, sem arredondar antes das comparações.

Política inicial: quatro cadeias, R-hat **menor que** 1,01, ESS bulk e tail de ao
menos 100 por cadeia, zero divergências e MCSE da média/SD não superior a 0,05.
O modo científico exige ao menos 1.000 draws por cadeia por padrão. O classificador
legado também sinaliza aquecimento ou draws abaixo de 400 como execução curta.
Contagens são requisitos operacionais, jamais critérios suficientes de aprovação.
Os valores são política do projeto, não limiares universais.

Parâmetros livres com diagnósticos indefinidos permanecem visíveis e impedem
aprovação completa. Nós fixos só ficam fora dos critérios MCMC quando o prior
determinístico nativo (ou a referência geográfica nacional) declara o valor e
todas as amostras confirmam esse valor. Cadeias livres constantes não recebem
essa exceção. O relatório preserva resumos por parâmetro e posições reais de até 128
draws por cadeia para até 64 parâmetros escalares. As estatísticas usam todas as
amostras. Truncamento de traços é declarado; a inspeção visual é tarefa humana.

PPC usa distribuições de **observações**, separadas dos intervalos de média
condicional. PyMC usa sua distribuição preditiva em escala original. No adaptador
nacional Meridian, o worker gera réplicas Gaussianas com o sigma posterior e o
transformador inverso de KPI nativos. Isso pressupõe o modelo observacional
Gaussiano atual, não é uma implementação genérica multigeográfica. O teste usa
somente o holdout observado original, nunca o placeholder de pré-processamento.
Cobertura pontual, largura, discrepâncias de média/dispersão e autocorrelação
residual são descritivos. Probabilidades de cauda preditivas não são p-valores
frequentistas e pontos temporais não são repetições independentes.

Refits pré-especificados variam sementes e, quando há controles, omitem o primeiro
controle como teste de estresse. O relatório compara parâmetros de efeito nas
unidades nativas e previsões, sem escolher vencedor pelo holdout. Omissão não é
recomendação para retirar confundidores. Priors/configuração efetiva são
preservados; o protocolo não afirma testar todas as famílias de prior ou likelihood.

## Robyn e Ridge

Não se calculam critérios MCMC para esses motores. Robyn preserva os resumos de
convergência da busca multiobjetivo (`errors` e mensagens nativas), coeficientes
selecionados, trials e iterações. O protocolo de busca extensa usa cinco trials e
2.000 iterações por trial, além de refits e consistência das estimativas. Quantidade
de busca, sozinha, não aprova o modelo. Modelos antigos sem trajetória da busca
continuam consultáveis, com essa evidência declarada ausente.

Ridge reaproveita solver restrito, posto da matriz, decomposição, backtests
temporais e sensibilidade de adstock/saturação existentes. Adiciona refits de
regularização e omissão de controle. O spread relativo é um critério configurável
do protocolo, não uma prova de identificabilidade. Não se comparam coeficientes
nativos de motores diferentes como se compartilhassem unidades ou interpretação.

## Monte Carlo com verdade conhecida

`monte_carlo` executa o Ridge real, sem substituição de resultados. O DGP tem
adstock normalizado, Hill, controles e ruído declarados. A verdade fica fora das
colunas fornecidas ao ajuste. O estimando é a diferença média no holdout sob aumento
de 10% em um canal ao longo de todo o histórico, incluindo seu carryover.

São dez cenários: bem especificado, efeito nulo, colinearidade, confundidor
omitido, ruptura de tracking, caudas pesadas, adstock mal especificado, variação
fraca, KPI ausente e investimento constante. Cada repetição registra semente
independente derivada de `SeedSequence`, hash dos dados, configuração, solver,
efeito verdadeiro, estimativa e intervalo condicional.

O relatório mede viés, RMSE, cobertura nominal de 90%, MCSE de viés/cobertura e
intervalo Wilson para a cobertura. Falhas permanecem no denominador tentado;
cobertura usa o denominador de intervalos disponíveis. Cobertura zero não vira
ausência de informação: o intervalo Wilson mantém incerteza mesmo quando o MCSE
plug-in é zero. Baixa variação pode produzir intervalos largos com alta cobertura
e estimativas inúteis; cobertura isolada não aprova o método.

A avaliação exige os cenários bem especificado e nulo, pelo menos 100 repetições
válidas por padrão e tolerância de cobertura pré-declarada (0,05 por padrão).
Limites Wilson com correção de Bonferroni entre os estimandos centrais evitam
tratar a frequência estimada como certeza. Se até o limite superior ficar abaixo
de 0,90 menos a tolerância, há reprovação; se o limite inferior não alcançar esse
valor, a precisão permanece inconclusiva. Limites substantivos de viés e RMSE
também precisam ser declarados para aprovação. Falhas centrais não são descartadas.
A classificação estatística incorpora essa avaliação de incerteza: um bom ajuste
pontual não anula subcobertura. O resultado vale somente para os DGPs estudados.

Os intervalos são bootstrap residual em blocos, condicionais às formas fixadas.
A restrição não negativa e a regularização podem causar subcobertura no efeito
nulo. Esta suíte não transforma intervalos preditivos nativos em intervalos de
efeito causal, nem declara equivalência entre parametrizações dos quatro motores.

## Experimentos, falsificação e calibração

Use resultados de `analyze_experiment` persistidos. A camada reconsulta fontes e
planos por hash, recusa origem incompatível e exige o mesmo KPI para validação do
modelo. Placebos e controles negativos usam intervalos e margem de equivalência
substantiva declarada; p-valor alto, sozinho, não comprova ausência de efeito.
Papéis dos controles, janelas e multiplicidade exigem revisão do desenho.

Hipóteses de randomização, interferência, confundimento, controles pós-tratamento,
positividade, mensuração, pré-especificação e acompanhamento ficam explícitas.
SRM, perdas, guardrails e falsificações contraditórias não são apagados por uma
declaração de randomização. A grade de viés representa **viés aditivo hipotético**
nas unidades da diferença entre braços; não estima confundimento não observado.

Calibração opcional reaproveita a reponderação bootstrap Ridge. Deriva lift e erro
padrão do experimento, exige origem/KPI/unidades compatíveis, explicação da
transformação de escopo e declarações de população/janela. Dados reais requerem
autorização do host e revisão declarada. A evidência usada para calibrar deve ser
disjunta da usada para validar/falsificar. A transformação continua dependente de
hipóteses, os pesos não são um posterior Bayesiano e o modelo não é alterado.
Refits experimentais nativos e integração GeoX não são declarados implementados.

## Uso MCP e dashboard

```json
{
  "model_id": "meu-modelo",
  "backend": "ridge",
  "scientific": {
    "refit": true,
    "seeds": [17, 29],
    "regularization": [0.01, 0.1, 1.0],
    "monte_carlo": {"replications": 100, "bootstrap_samples": 40},
    "experiment_result_ids": [],
    "placebo_result_ids": [],
    "negative_control_result_ids": []
  }
}
```

Envie o objeto em `request` para `audit_model`. Depois passe `scientific_report_id`
para `get_analysis` ou `export_analysis`. Relatórios incompatíveis com o modelo ou
dataset são recusados. `get_growth_artifact` também consulta o relatório. O
dashboard mostra as três dimensões, traços selecionáveis, PPC e tabelas de Monte
Carlo, com download JSON e exportação Markdown. Relatórios JSON não incluem o
binário nativo. O endpoint MCP HTTP mantém autenticação e isolamento por tenant;
reader pode consultar evidência, mas não criar relatórios científicos. Só o
dashboard local mantém acesso direto, conforme política anterior.

## Reprodução e CI

Os ajustes novos usam calendário explícito: tendência e Fourier anual no Meridian,
além do intercepto nativo, e tendência com o Fourier nativo no PyMC. O perfil
`baseline="legacy"` permite ablação explícita. Controles do PyMC são padronizados
apenas com o treinamento; origem temporal e transformações são persistidas e
reutilizadas na restauração e no futuro. `prior_scale_multiplier` permite
sensibilidade pré-especificada e `target_accept` chega ao amostrador de cada motor.
O mapa de opções Meridian é imutável porque o backend JAX usa argumentos estáticos.
O NetCDF PyMC usa compressão zlib sem perda, preservando grupos, cadeias e draws.
Somente arrays determinísticos por data, que o grafo recompõe, são omitidos;
todas as variáveis aleatórias são retidas. Os oito arrays retidos na prova de
persistência foram comparados bit a bit, e as predições restauradas com
`rtol=atol=1e-7`. `--refit-draws` permite um orçamento de refit declarado
separadamente, nunca menor que o mínimo do protocolo. Cada refit tem seu próprio
diagnóstico, incluindo métricas numéricas, e pode reprovar o resultado global.

Refits científicos são artefatos imutáveis próprios, com dados, configuração,
fontes e metadados dos runtimes na identidade. `reused=true` identifica reuso,
sem contar o mesmo fit como nova amostra independente. Não modifique código ou
dependências durante uma execução: uma mudança detectada invalida a captura;
o ledger preserva os refits já concluídos. Falhas do worker conservam um log
privado limitado, inclusive em timeout, saída ausente/excessiva, JSON inválido,
contrato incorreto ou erro de leitura/escrita. Nenhuma falha troca de motor.

### Intervalos condicionais Ridge

O bootstrap residual restrito original continua identificado como
`legacy_percentile`. Na fronteira de efeito zero, suas estimativas não negativas
e percentis estritamente positivos podem produzir cobertura zero. A alternativa
`projected_hc3` usa OLS sem penalização em desenho de posto completo, covariância
sandwich HC3 e projeção monótona do conjunto de confiança no espaço não negativo.
`projected_hac` usa Newey-West/Bartlett com três lags, preservando a correção de
alavancagem. Projeção pode ser conservadora em zero; não corrige confundimento,
tracking ou especificação incorreta. Desenhos sem posto completo recusam o
intervalo em vez de fabricar precisão por pseudoinversa.

As previsões pontuais e o viés/RMSE principais continuam sendo do Ridge restrito;
o intervalo alternativo vem da inferência OLS separada. `method_comparisons`
compara a cobertura dos três conjuntos nas mesmas repetições, sem reclassificar
draws bootstrap como posteriores ou considerar o novo estudo uma validação dos
draws legados. A simulação expõe o contraste OLS HC3/HAC em
`conditional_linear_confidence`, separado do resultado pontual Ridge e de seus
intervalos bootstrap anteriores. Shapes e controles permanecem condicionais.

### Recuperação nativa e experimentos agrupados

`scientific.native_monte_carlo` executa fits reais no motor solicitado e mede
contrastes de médias condicionais sob aumento histórico de 10% em um canal,
incluindo carryover. Meridian e PyMC usam os mesmos draws conjuntos nos dois
cenários; ruído de observações independentes não é incerteza de efeito.
Robyn usa suas transformações nativas e mantém a inflexão Hill de referência;
oferece estimativa pontual e cobertura indisponível. Quantis de soluções da busca
não são intervalos de confiança.

Cada avaliação registra as datas efetivas do teste, versões, configuração,
diagnósticos e a verdade sintética nessas mesmas datas. O DGP Hill conhecido é
uma especificação deliberadamente diferente da saturação Logistic do PyMC.
Priors positivos contínuos também podem excluir zero exato; esse problema de
calibração não desaparece aumentando draws. Amostras pequenas, execução incompleta,
intervalos ausentes ou tolerâncias de negócio não declaradas não certificam
cobertura. O contrato público exige quatro cadeias e ao menos 1.000 draws e
warmup; os testes de transporte reduzidos têm escopo explicitamente distinto.

```powershell
.\.venv\Scripts\python.exe examples/scientific_protocol.py --backend google_meridian --native-replications 2 --skip-refits --output-dir evidence/minha-recuperacao-nativa
```

O workflow manual oferece `native_recovery` para execuções separadas por motor.
O timeout do cliente considera as chamadas sequenciais; cada processo continua
limitado a até uma hora. Dois fits por cenário só verificam execução e mostram
estimativas iniciais: a política de cobertura continua exigindo pelo menos cem
repetições e precisão Monte Carlo suficiente.

### Lotes Robyn que excedem o limite do endpoint

Chamadas MCP permanecem limitadas a uma hora por worker. O operador pode usar
`examples/robyn_offline_refit.py` para repetir um perfil DE sintético já
declarado, com teto explícito de duas horas e os mesmos limites de CPU/memória.
Esse CLI local usa o mesmo `robyn_worker.R`, não muda hiperparâmetros, critérios
de busca ou motor e não cria um endpoint de comandos arbitrários. Escolha um
diretório novo e registre também as tentativas que excederam o limite anterior.

```powershell
.\.venv\Scripts\python.exe examples/robyn_offline_refit.py --store var/robyn-de-comparison/data --model-id ID --seed 97 --timeout-seconds 7200 --output-dir var/novo-lote-de97
.\.venv\Scripts\python.exe examples/import_robyn_batch.py --store var/robyn-de-comparison/data --batch var/novo-lote-de97
```

Substitua `ID` pelo identificador do modelo DE de referência. O importador é
exclusivo do operador: confere hashes, identidade atual do runtime/código,
dataset sintético, configuração e restauração nativa antes de escrever um
modelo novo no ledger imutável. Não importa lotes reprovados operacionalmente,
não sobrescreve modelos e não aceita arquivos arbitrários via MCP. Após importar,
`audit_model` reutiliza explicitamente os refits; o transporte de origem fica
registrado como `local_native_r_batch`. A importação não aprova a estatística.

Planos de experimento aceitam `analysis_unit="paired"` com `pair_column` para
pares completos de unidades distintas (uma em cada braço) e teste t da diferença
pareada; o desvio de planejamento deve ser o das diferenças. `analysis_unit="cluster"`
com `cluster_column` usa médias de clusters com pesos iguais e Welch entre
clusters; o desvio de planejamento deve ser o das médias de clusters. Repetir
indivíduos dentro dos mesmos clusters não aumenta os graus de liberdade.
O estimando passa a ser o efeito médio por cluster, não por indivíduo.

Esses dois desenhos suportam resultados contínuos e guardrails contínuos;
desfechos binários agrupados, razões de custo, pares incompletos, clusters em
mais de um braço e desenhos combinando par/cluster são recusados explicitamente.
Os hashes continuam referindo-se aos dados e ao plano originais. SRM é calculado
nos clusters; em pares completos a proporção é estrutural e SRM fica não aplicável,
sem p-valor fictício. A calibração automática permanece conservadora e não aceita
evidência sem os critérios de qualidade existentes. Nenhum rótulo importado
comprova randomização, ausência de interferência ou transportabilidade.

```powershell
.\.venv\Scripts\python.exe examples/scientific_protocol.py --backend ridge --replications 100 --output-dir evidence/minha-validacao-ridge
.\.venv\Scripts\python.exe examples/scientific_protocol.py --backend all --replications 100 --output-dir evidence/minha-validacao-completa
```

O segundo comando precisa dos três runtimes externos e do R configurados.
`--transport-smoke --skip-refits --replications 2` permite verificar transporte e
contratos rapidamente; não é validação analítica. As saídas não sobrescrevem
pastas existentes. O CLI usa o cliente MCP oficial via stdio, registra hashes das
fontes antes/depois e preserva componentes já concluídos em `partial.json`.

`--reuse-store caminho-local` é uma opção exclusiva do operador do exemplo: copia
para uma pasta nova somente modelos sintéticos com hashes, semente e configuração
compatíveis. Restauração, diagnóstico e refits continuam sendo executados; o
relatório registra quais ajustes foram reaproveitados. Isso não adiciona acesso
a caminhos arbitrários às ferramentas MCP. Versões do runtime de treinamento
(quando gravadas no modelo) e do diagnóstico são preservadas separadamente.
Modelos legados não ganham versões de treinamento presumidas retrospectivamente.
O timeout do processo R respeita o orçamento validado do worker principal,
reservando tempo para encerramento e gravação da resposta.

O workflow manual `scientific-validation.yml` reutiliza os runtimes fixados e
executa amostragem extensa, refits e Monte Carlo. Sucesso do workflow significa
que executou/registrou o protocolo; os resultados científicos podem ser reprovados
ou inconclusivos. Os testes rápidos, gates de cobertura e ciclo nativo curto
permanecem no CI normal. Não há execução de campanhas ou deploy.

O manifesto `requirements/robyn-r-win-binaries.json` usa o snapshot oficial Posit
CRAN de 23/10/2026, com as 115 versões anteriores e SHA256 por arquivo. O instalador
valida URLs, data e hashes, com cache separado por snapshot e sem fallback para
`latest` ou para um arquivo de hash diferente. Para reconferência pelo mantenedor,
`python examples/freeze_r_binaries.py --snapshot 2026-10-23` usa as versões do
manifesto rastreado; `--packages-csv` permite uma atualização deliberada da lista.
Revisar o diff e executar os ciclos nativos antes de adotar outro snapshot.

## Referências

- [Stan: análise posterior e R-hat](https://mc-stan.org/docs/reference-manual/analysis.html).
- [Stan: ESS bulk/tail e cadeias](https://mc-stan.org/rstan/reference/Rhat.html).
- [Meridian: saúde do modelo](https://developers.google.com/meridian/docs/post-modeling/health-checks). O limiar de R-hat do health card difere da política interna mais conservadora.
- [Meridian: hipóteses causais](https://developers.google.com/meridian/docs/causal-inference/about-mmm-causal-inference-methodology).
- [Meridian: calibração](https://developers.google.com/meridian/docs/advanced-modeling/roi-priors-and-calibration).
- [Robyn: recursos e convergência da busca](https://facebookexperimental.github.io/Robyn/docs/features/).
- [PyMC-Marketing: percurso de modelagem](https://www.pymc-marketing.io/en/latest/guide/mmm/mmm_learning_path.html).
- [GeoX](https://developers.google.com/meridian/geox?hl=pt-br), referência metodológica externa, sem integração declarada neste adaptador.
