# Correções científicas — protocolo de investigação

Base: PR #9, revisão `976c08a`; branch de correções `fix/scientific-inference`.
Os limites de R-hat, ESS, MCSE, divergências e cobertura do protocolo anterior
permanecem inalterados. Não há merge automático ou uso de dados reais.

## Causas investigadas e escolhas anteriores à validação nova

- Ridge: percentis de refits restritos não são conjuntos de confiança válidos na
  fronteira zero. Comparar o método legado com inferência OLS sem penalização,
  covariância HC3/HAC e projeção do conjunto sobre o espaço de sinal permitido.
  A inferência é condicional às formas e não corrige confundimento omitido.
- Meridian: quatro nós temporais não representam adequadamente a sazonalidade do
  gerador de demonstração. Avaliar desenho de calendário explícito, um intercepto
  nativo e controles. Parâmetros fixos só são excluídos dos critérios MCMC quando
  a distribuição nativa declara sua fixação e os draws confirmam o valor.
- PyMC: o adaptador anterior inclui Fourier anual, mas omite tendência e não
  centraliza os controles. Avaliar tendência e padronização exclusivamente no
  prefixo de treinamento, com estado persistido para previsão/restauração.
- Robyn: calendário já existe e será reaproveitado. Preservar os avisos nativos,
  realizar as três otimizações extensas pendentes e comparar contribuições/ROAS.

## Coortes e configuração pré-especificada

1. Desenvolvimento Ridge: semente 1103, 1.000 repetições por DGP central; comparar
   os três intervalos nas mesmas repetições. Validação independente: semente 7919.
2. Adversos Ridge: semente 1104; manter colinearidade, confundimento omitido,
   ruptura de tracking, baixa variação, caudas pesadas e adstock incorreto.
3. Comparação diagnóstica Bayesiana: dataset de demonstração de semente 42,
   quatro cadeias × 2.000 draws após 2.000 de ajuste; configurações declaradas,
   target_accept PyMC de 0,95; nunca eleger a configuração pelo holdout.
4. Sensibilidade: sementes 61 e 73, multiplicadores de prior 0,5/2, omissão do
   primeiro controle e ablação `legacy` com o mesmo orçamento. Sem vencedor.
5. Validação Bayesiana independente: dados de semente 10142, perfil de calendário
   já declarado, sem seleção pelo conjunto de teste.
6. Robyn: reutilizar o ajuste extenso imutável de cinco trials × 2.000 iterações
   como referência; completar refits independentes nas sementes 59/71 e omissão
   de controle. Reuso de fits existentes deve ser explícito, sem contá-los como
   novas amostras. Preservar toda tentativa e falha.
7. Estudos nativos: utilizar contrastes condicionais nas mesmas amostras
   posteriores e intervenções de 10% sobre todo o histórico, com carryover.
   A busca pontual Robyn não fornece, por si, uma distribuição de incerteza de
   efeitos; quantis entre soluções de busca não serão rotulados como confiança.

Viés/RMSE não ganham tolerâncias retrospectivas. Precisão Monte Carlo insuficiente,
falha de identificação e ausência de intervalo continuam inconclusivas ou
reprovadas, conforme os critérios existentes. Os resultados de desenvolvimento
não substituem as coortes independentes, nem certificam efeitos empresariais.

Comparação adicional de busca Robyn, declarada antes da execução: algoritmo
NGOpt, semente 83, cinco trials × 5.000 iterações, mantendo o mesmo espaço de
hiperparâmetros e a seleção interna por validação. O resultado entra como
alternativa de busca, sem escolher vencedor pelo holdout nem substituir os
avisos nativos das outras buscas. Os critérios nativos de mediana/desvio padrão
permanecem intactos, mesmo se a alternativa também for reprovada.

A tentativa NGOpt foi rejeitada pelo runtime antes da primeira iteração:
Nevergrad 1.0.12 não oferece `set_objective_weights` nesse otimizador, exigido
pelo Robyn 3.12.1. A API agora restringe os algoritmos a TwoPointsDE e DE;
ambos possuem o método nativo. Comparação substituta declarada antes de executar:
DE, semente 83, cinco trials × 5.000 iterações, com o restante do desenho igual.
A falha NGOpt continua registrada; não houve fallback.

Precisão PyMC: após 2.000 draws/cadeia, o MCSE relativo da média de
`saturation_beta[spend_social]` foi 0,05256, acima de 0,05. Execução suplementar
pré-declarada: mesmo dataset/priors/semente 42, quatro cadeias × 4.000 draws e
2.000 warmup, sem seleção pelo holdout. O critério de MCSE não muda. A nova
persistência preserva todas as variáveis aleatórias, grupos, cadeias e draws;
arrays determinísticos por data são recomputados pelo grafo nativo. A prova
com 2.000 draws preservou exatamente os oito arrays retidos; as previsões foram
comparadas com tolerâncias relativas e absolutas de `1e-7`;
o NetCDF caiu de 60.611.598 para 1.571.850 bytes. O teto operacional de amostragem
passa de 2.000 para 8.000; limites de diagnóstico e de arquivo não são afrouxados.

Replicação da busca DE: após a configuração pré-declarada de semente 83 atender
aos dois critérios nativos, executar sementes independentes 97 e 109 e ablação
do primeiro controle com semente 97, mantendo cinco trials × 5.000 iterações.
A seleção permanece por validação interna, sem escolher configurações pelo
holdout. Comparar todos os resultados, inclusive as reprovações TwoPointsDE.

As três tentativas via MCP das sementes 97/109 e da ablação 97 terminaram por
`TimeoutExpired` do R após 3.550 segundos, dentro do limite de 3.600 do worker;
nenhuma produziu resultado estatístico. Logs privados dessas falhas foram
preservados. Repetição operacional pré-declarada: mesmas configurações e sementes,
mesmo código R, em lote local do operador com teto de 7.200 segundos, CPU/memória
limitadas e sem ampliar o deadline do MCP. O importador confere identidade e
restauração antes de permitir reuso imutável; não escolhe refits por seus resultados.
