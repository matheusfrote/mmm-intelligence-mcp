# Correções científicas e limites de validação

Revisão: 4–5 de novembro de 2026. Base: PR #9 (`976c08a`).
Esta entrega usa exclusivamente dados sintéticos. Os resultados anteriores estão
preservados em [scientific-validation-results.md](scientific-validation-results.md).
As escolhas e as execuções suplementares estão registradas no
[protocolo de investigação](scientific-corrections-plan.md).

## O que mudou e o que os resultados permitem concluir

| Motor / diagnóstico | Antes, PR #9 | Após as correções | Interpretação |
| --- | --- | --- | --- |
| Ridge, cobertura do efeito nulo | 0% no estudo anterior | HC3 projetado: 95,3% / 95,2% / 96,3%, por canal, na coorte independente | Novo conjunto de confiança condicional, separado do estimador Ridge e do bootstrap legado |
| Meridian, cobertura PPC de 90% | 3,125% | 90,625%, dados de semente 42 | Melhora preditiva no gerador conhecido; sensibilidade e identificação ainda podem reprovar |
| Meridian, diagnósticos indefinidos | Nove escalares | Zero escalares livres indefinidos; nós fixos declarados são não aplicáveis | Constância de cadeia livre continua sendo falha; não há dispensa baseada apenas em desvio zero |
| PyMC, cobertura PPC de 90% | 37,5% | 87,5%, dados de semente 42 | Tendência e escala dos controles corrigidas, com transformação persistida |
| PyMC, MCSE relativo máximo | 0,05624 | 0,05256 com 2.000 draws; 0,03373 com 4.000 | O primeiro ajuste continuou reprovado; orçamento adicional, sem mudar o limite 0,05 |
| Robyn, busca TwoPointsDE | Ambos os objetivos sem convergência | Reprovações preservadas nos três refits extensos | Estabilidade entre soluções não substitui critérios nativos de otimização |

Os critérios de R-hat, ESS, divergências, MCSE, PPC e estabilidade não foram
afrouxados. Aumento do orçamento computacional não implica aprovação. O conjunto
de teste foi usado para avaliação declarada, sem selecionar configurações por
seu desempenho. Comparações na semente de desenvolvimento não substituem a
avaliação em dados independentes.

## Ridge: incerteza e cenários adversos

Percentis de bootstrap de estimativas penalizadas e restritas ao sinal positivo
não são intervalos válidos para testar efeito exatamente zero. O método antigo
continua identificável como legado e não suporta teste de efeito nulo.
Implementamos inferência OLS não penalizada com SVD, covariâncias HC3 e HAC
Bartlett/Newey–West, quantis t e projeção dos extremos sobre o espaço não negativo.
Posto deficiente, alavancagem extrema e graus de liberdade insuficientes provocam
abstenção. A inferência condiciona nas formas de adstock/saturação e nos controles.
HC3/HAC com quantis t são aproximações robustas de inferência; não oferecem
cobertura finita exata para qualquer processo temporal. A calibração é avaliada
nos DGPs declarados, não extrapolada para todo conjunto de dados.

Foram executadas 2.000 repetições de desenvolvimento (semente 1103), 2.000
independentes (7919), e 2.000 adversas (1104, 250 por cenário). A coorte
independente, com 1.000 repetições por DGP, encontrou:

| DGP / canal | Bootstrap legado | HC3 projetado | HAC projetado |
| --- | --- | --- | --- |
| Bem especificado / search | 84,6% | 92,3% | 90,2% |
| Efeito nulo / search | 0,2% | 95,3% | 94,5% |

O nível nominal é 90%; na fronteira zero a projeção pode produzir cobertura
conservadora. Os números acima comparam métodos nas mesmas repetições. As
estimativas pontuais e o viés/RMSE principais ainda são do Ridge restrito;
os intervalos OLS não são intervalos em torno de seu estimador penalizado.
No search, viés/RMSE foram 0,12984/4,02266 no DGP bem especificado e
1,59549/2,90345 no nulo. Não foram inventadas tolerâncias comerciais para esses
valores depois de observar os resultados.

Nos adversos, a cobertura HC3 do search foi 0% sob confundimento omitido,
0,8% com ruptura de tracking e 0% com adstock incorreto. Caudas pesadas tiveram
90,4%. Baixa variação teve 91,6%, porém largura média de intervalo 5.250,85:
cobertura sozinha não garante precisão útil. Colinearidade tornou a inferência
indisponível; target ausente e mídia constante foram recusados. As falhas não
foram convertidas em aprovação por R² ou por cobertura de código.

## Meridian e PyMC: amostragem, PPC e sensibilidade

No Meridian, a configuração de calendário usa tendência/Fourier, controles e um
intercepto nativo; a configuração anterior permanece como ablação `legacy`.
O adaptador agora transmite efetivamente `target_accept` ao argumento nativo
`dual_averaging_kwargs`, em estrutura imutável exigida pelo JAX. Priors
determinísticos só são dispensados de MCMC após confronto com os draws.
O novo calendário tem quantidade diferente de nós fixos; não se trata de
ocultar os nove valores indefinidos históricos.

O ajuste Meridian de quatro cadeias × 2.000 draws, com 2.000 de adaptação e
2.000 de burn-in por cadeia, encontrou R-hat máximo 1,00218, ESS bulk/tail
mínimos 1.389,68/1.437,49, zero divergências e MCSE relativo 0,02858.
Os seis refits terminaram, mas uma semente e o prior ampliado tiveram
divergências; a ablação legacy teve PPC 0%. A amplitude relativa de ROI do
vídeo foi aproximadamente 0,776, acima do limite 0,5. Portanto a classificação
estatística global continua **reprovada**. Na semente independente de dados
10142, o PPC foi 78,125% e houve uma divergência: reprovação preservada.

No PyMC, tendência e escala dos controles são calculadas usando somente o
prefixo de treinamento e persistidas para restauração e projeção. Os contrastes
de efeitos usam a média condicional `mu` nos mesmos draws, com transformação
inversa oficial. O contrato recusa links não suportados; não subtrai predições
com ruído independente para representar incerteza de efeitos.

O ajuste de precisão PyMC, quatro cadeias × 4.000 draws e 2.000 warmup,
encontrou R-hat 1,00090, ESS bulk/tail 3.291,16/2.312,45, zero divergências,
MCSE relativo 0,03373 e PPC 87,5%. Cinco dos seis refits de 2.000 draws
atenderam aos diagnósticos; a ablação legacy teve PPC 40,625%. O relatório
global conserva **reprovação por diagnóstico de refit**.

Na semente independente de dados 10142, com o mesmo perfil pré-declarado de
4.000 draws, o PyMC teve R-hat 1,00098, ESS bulk/tail 2.572,85/2.144,29,
zero divergências e PPC 78,125%. O MCSE relativo foi 0,05027094, acima de
0,05: **reprovado**, mesmo próximo do limite. A execução não foi repetida
até obter aprovação e seu holdout não selecionou outra configuração.

Cada refit registra seus próprios R-hat, ESS, divergências, MCSE e PPC. O sistema
não aprova sensibilidade apenas porque os coeficientes parecem estáveis ou o
ajuste primário passou. Resultados ausentes são inconclusivos.

## Robyn: resultados dos refits extensos

A comparação DE de semente 83, cinco trials × 5.000 iterações, atendeu aos dois
critérios nativos. Isso não se repetiu nos três refits pré-declarados:

| Perfil DE, 5 × 5.000 | NRMSE | DECOMP.RSSD, critério da mediana final |
| --- | --- | --- |
| Semente 83 | Convergiu | Convergiu: 0,025 ≤ 0,029 |
| Semente 97 | Convergiu | Reprovado: 0,022 > 0,021 |
| Semente 109 | Convergiu | Reprovado: 0,037 > 0,00008 |
| Semente 97, sem primeiro controle | Convergiu | Reprovado: 0,024 > 0,0058 |

São valores arredondados das mensagens nativas; os traces completos estão nos
recibos. Os três refits tiveram amplitude relativa máxima de coeficiente 0,23288,
ROAS/contribuição 0,30436, proporção de contribuição 0,30495 e previsão 0,01072.
Esses valores ficaram abaixo de 0,5, porém o relatório global permanece
**reprovado por diagnóstico dos refits**. Estabilidade das estimativas não
anula a reprovação do objetivo de decomposição.

As primeiras tentativas desses três perfis excederam 3.550 segundos do R no
worker MCP de uma hora e não produziram resultado estatístico. As mesmas
configurações foram repetidas em lote local limitado a duas horas, mantendo
CPU/memória, código R e critérios. Todos os lotes concluíram operacionalmente.
Os modelos foram restaurados e importados no ledger sem sobrescrita; o SDK
oficial executou `audit_model`, `get_analysis` e `export_analysis`, com os três
refits explicitamente reutilizados. A origem offline consta nos artefatos.

A tentativa anterior NGOpt foi recusada antes da primeira iteração por ausência
de `set_objective_weights` no Nevergrad 1.0.12. A API passou a aceitar somente
TwoPointsDE e DE, ambos verificados, sem fallback. As falhas de infraestrutura,
as reprovações TwoPointsDE e os três resultados DE reprovados foram preservados.
Não foram sorteadas novas sementes até obter aprovação. Avançar exige um novo
protocolo pré-declarado de busca/identificação e evidências de dados adequadas;
não há justificativa para dispensar os critérios após observar esses resultados.

## Recuperação de efeitos nativos

Cada motor executou quatro fits reais no piloto: dois por DGP bem especificado
e dois por DGP nulo, além de quatro recusas esperadas de dados inválidos.
Meridian/PyMC usaram quatro cadeias × 1.000 draws e warmup; Robyn, cinco
trials × 2.000 iterações. Não houve substituição de execução por mocks ou Ridge.

Os contrastes correspondem a aumento de 10% em um canal ao longo do histórico,
com carryover, avaliados nas datas efetivas do teste. O DGP Hill e a saturação
Logistic do PyMC são especificações diferentes, declaradas. Priors positivos
contínuos podem excluir zero exato: a cobertura nula Bayesiana observada no
piloto continua 0%, sem aprovação. O Robyn fornece efeito pontual, sem intervalo
frequentista/posterior artificial derivado das soluções da busca.

Dois fits por cenário não estimam cobertura com a precisão mínima exigida;
viés/RMSE não têm tolerâncias comerciais pré-declaradas. Os pilotos são
**reprovados ou inconclusivos**, conforme cada diagnóstico, e não certificam
efeitos reais. A suíte permite os dez cenários adversos; validar sua calibração
nativa extensamente exige novas execuções com pelo menos cem repetições por DGP.

## Correções operacionais e metodológicas

- Refits imutáveis têm identidade de dataset, configuração, código e runtime.
  Reuso aparece explicitamente e não conta como nova repetição independente.
  Alteração de fontes durante treinamento provoca recusa do resultado.
- Persistência PyMC usa compressão NetCDF sem perda e omite somente arrays
  determinísticos por data recomputáveis pelo grafo. Todos os grupos, variáveis
  aleatórias, cadeias e draws são preservados. Na prova de 2.000 draws, oito
  arrays retidos ficaram idênticos bit a bit; previsão restaurada foi comparada
  com `rtol=atol=1e-7`. O arquivo caiu de 60.611.598 para 1.571.850 bytes.
- Falhas de worker, timeout e respostas inválidas preservam log privado limitado.
  A causa do primeiro encerramento PyMC sem log não foi recuperada e permanece
  desconhecida; não é atribuída retrospectivamente a memória ou tamanho.
- O pacote instalado fora do checkout não localizava as bibliotecas R. A variável
  de host `MMM_R_LIBRARY` corrige a localização e entra no hashing de proveniência.
  O teste real do wheel restaurou o modelo Robyn e retornou 30 períodos de previsão;
  configuração de biblioteca inexistente é recusada sem fallback.
- O teste de cobertura R podia selecionar um pedido de efeito como previsão e
  aceitar um campo ausente. A seleção agora exige a operação correta, e o escopo
  e o vetor de previsão são verificados explicitamente. A nova execução mediu
  100% das linhas e 28/28 decisões/saídas de laço, sem excluir fontes.
- Os contrastes Robyn foram comparados com a decomposição nativa: erro máximo
  absoluto zero nos três canais na prova de referência.
- Experimentos contínuos pareados usam diferenças entre pares completos;
  clusters usam médias de clusters com pesos iguais e graus de liberdade de
  clusters. Desenhos sem suporte são recusados. SRM em pares completos é
  não aplicável, sem p-valor inventado.
- Dashboard e relatórios mostram as três classificações independentes, PPC,
  cadeias, refits, métodos de intervalo e limitações. Autenticação remota e
  acesso direto ao dashboard local são preservados.

## Evidências e reprodução

### Verificações operacionais desta revisão

- Suíte base Windows final: **807 testes aprovados**, nove opcionais executados
  separadamente nos ambientes correspondentes, sem falhas de teste.
- Oito casos nativos de transporte/admissão foram executados nos três runtimes,
  incluindo as duas configurações legacy. O teste de tradução das opções do
  amostrador foi executado com a dependência imutável do runtime Meridian, sem
  instalar ou modificar dependências. Esses casos não certificam convergência.
- SDK oficial via stdio: 45 ferramentas executadas, três prompts, um recurso,
  reinício/persistência e previsão futura PyMC verificados; sem reuso de recibos
  para substituir a execução integral desse ciclo.
- Dashboard: 100% de linhas/branches JavaScript no teste em navegador, incluindo
  os quatro motores. R: 100% das expressões/linhas e 28/28 branches `if`/`for`
  no escopo de instrumentação documentado, com execução nativa.
- Ruff, mypy e Bandit aprovados; auditorias dos quatro locks Python e do lock npm
  sem vulnerabilidades conhecidas reportadas. Isso não constitui auditoria
  completa de vulnerabilidades de pacotes R ou de produção externa.
- Wheel: instalação em venv limpa, descoberta de 45 ferramentas, 23 chamadas
  locais e reinício testados; restauração Robyn também exercitada fora do checkout
  com `MMM_R_LIBRARY` explícita.

O gate Python continua exigindo 100% de linhas **e** branches e hashes idênticos
das fontes executadas. Capturas de fontes alteradas são rejeitadas; não há novas
exclusões para obter aprovação. Branches específicos de Linux e a matriz
Windows/Linux/macOS são verificados no CI da PR; não se presume aprovação remota
a partir dos resultados locais.

Para reproduzir uma coorte Ridge publicada, em ambiente instalado, use a
configuração completa do respectivo JSON. Por exemplo, este código de operador
executa a coorte independente e recusa sobrescrever o destino:

```python
import json
from pathlib import Path
from mmm_intelligence.monte_carlo import run_study
from mmm_intelligence.schemas import MonteCarloProtocol

receipt = Path("docs/validation/scientific-corrections/ridge-independent.json")
config = MonteCarloProtocol.model_validate(json.loads(receipt.read_text())["configuration"])
result = run_study(config)
with Path("var/reproduced-independent.json").open("x", encoding="utf-8") as output:
    json.dump(result, output, allow_nan=False)
```

Substitua o nome por `ridge-development.json` ou `ridge-adversarial.json` para as
demais coortes. Reserve processamento para as repetições efetivas; não são mocks.
Para os nativos, gere o dataset com a semente registrada no recibo, use
`train_backend` com a configuração registrada e `audit_model` com o protocolo
correspondente. O CLI público documentado no guia executa esses mesmos contratos
pelo SDK oficial; os refits ficam no ledger imutável do diretório autorizado.

Os JSONs em [validation/scientific-corrections](validation/scientific-corrections)
preservam métricas, sementes, configurações, versões e hashes dos recibos de
origem. Não incluem modelos pesados, dados reais ou credenciais. Os agregados
Ridge preservam todas as configurações necessárias para reproduzir os estudos;
os registros completos das 6.000 repetições permanecem no armazenamento local.
O [guia científico](scientific-validation.md) documenta o CLI e os workflows.

A [revisão complementar das referências](reference-repository-review.md) registra
como a lista de 211 repositórios fornecida pelo usuário foi avaliada, os commits
examinados e as escolhas preservadas na implementação.

**Falta para uma afirmação empresarial:** experimentos reais autorizados,
randomização e interferência verificáveis, revisão das hipóteses de identificação,
controles negativos/placebos adequados, precisão de efeito suficiente e análise
de transportabilidade. Sucesso operacional, convergência numérica, PPC e estudos
sintéticos não fornecem esses elementos automaticamente.
