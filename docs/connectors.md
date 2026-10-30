# Fontes e conectores

Nenhuma conta foi conectada. `connector_status` retorna `contract_only_not_implemented`
e `live_verified=false` para Google Ads, Meta Ads, GA4, TikTok Ads, Microsoft Advertising,
vendas, CRM, e-commerce, SQL e warehouses. CSV/JSON são os caminhos funcionais atuais.

`MarketingSource.fetch_page(start, end, cursor)` é uma interface Python. `SourceBatch`
declara fonte/versão, moeda, fuso, granularidade, watermark, registros, totais declarados,
referência de autorização e origem sintética. A referência nunca deve conter token.
O contrato não autentica uma fonte. `reconcile_batches` verifica offline até 100 lotes/
10 mil linhas, campos financeiros/fuso/granularidade compatíveis, números finitos,
totais com tolerância absoluta explícita até 0,01 e duplicidades por fonte+granularidade.
Não soma páginas sobrepostas nem converte moeda. O recibo inclui hashes dos lotes e
`source_authenticated=false`. Testes usam respostas fabricadas.

Cada adapter futuro deve usar API oficial/escopo de leitura, cofre de credenciais do
host, renovação de autorização, limite de páginas/retries, Retry-After, backoff com
jitter e timeout. Registrar falhas sem dados sensíveis. Reconciliar com relatórios da
fonte antes de salvar watermark; falha parcial não avança sincronização. Histórico
precisa identificar conta autorizada, versão da API, janela, granularidade e atualização.
Esses mecanismos de API não estão implementados pelo contrato offline.

Prioridade: vendas/KPI + Google Ads/Meta Ads; GA4 auxilia reconciliação, mas conversões
atribuídas pelas plataformas não substituem KPI empresarial deduplicado. Aceite exige
testes de paginação, expiração, 429, falha parcial, idempotência, duplicidade e totais,
seguidos de execução real autorizada. Faltam adapters, autenticação e dados reais.

Parquet não foi acrescentado: não é necessário ao fluxo de até 10 mil linhas e traria
dependência binária. MCP recebe conteúdo inline; nunca caminhos/URLs de arquivos.
