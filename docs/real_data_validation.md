# Protocolo de validação com dados reais

Bloqueado pela ausência de base empresarial e autorização de fonte. Todos os
experimentos V4 são sintéticos. Nenhuma conta foi acessada.

1. Registrar proprietário, finalidade, consentimento, retenção e ambientes permitidos.
   Definir KPI, moeda, devoluções/impostos, fuso, frequência, população e canais.
2. Reconciliar gasto e KPI com origem; distinguir exposição, gasto e conversões
   atribuídas. Identificar tracking, preço, promoções, oferta e confundidores pelo
   conhecimento de negócio antes de observar rankings.
3. Preservar extração e hashes; mapear colunas e declarar agregação. Não imputar ou
   descartar silenciosamente. Executar import_csv/import_dataset e data_quality.
4. Somente após consentimento, configurar MMM_ALLOW_REAL_DATA=true no host e uma
   authorization_reference que identifique a autorização sem conter segredo.
5. Predefinir treino/validação/teste e baselines; reservar teste final, refazer seleção
   dentro dos backtests e registrar inputs conhecidos por origem. Não selecionar
   repetidamente configurações no mesmo teste final.
6. Revisar hipóteses/DAG, confundimento, colinearidade, histórico e sazonalidade;
   comparar especificações e priors. Bom ajuste não identifica contribuição causal.
7. Revisar cadeias/traços, R-hat, ESS, divergências, PPC e sensibilidade. A classificação
   automática cobre apenas parte disso. Smoke curto não basta; Robyn exige avaliação
   própria de busca/trials, não critérios MCMC.
8. Obter experimento de incrementalidade independente com população, intervenção,
   estimando e incerteza predefinidos. Rever transporte para os períodos/canais/verbas.
   Calibração numérica não valida desenho experimental.
9. Predefinir avaliação posterior, limites de perda e parada. Aprovação e execução
   de campanhas são externas a este MCP.

Aceite: origem, reconciliação, transformações, validação temporal, diagnóstico,
sensibilidade e experimento revisados pelos responsáveis do negócio e do método.
Não há escore arbitrário de confiança. As ferramentas atuais mantêm
business_recommendation_eligible=false e não alteram campanhas.
