# Roadmap após a V4

Estado executado: [entrega V4](v4-delivery.md). O plano original permanece no histórico
Git; relatórios 0.1–0.3 são históricos. Não há prazos ou automações agendadas.

| Prioridade | Pendência | Dependência e aceite |
|---|---|---|
| P0 | Publicar branch/release/PyPI | Autorização correspondente, revisão, CI do commit; conta/Trusted Publisher para PyPI |
| P0 | Executar V4 nas nove combinações CI | Publicação autorizada; resultados 0.3.1 não certificam V4 |
| P0 | Proteger main | Aprovação das regras, revisão viável para mantenedor solo e nomes reais dos checks |
| P0 | Validar decisões empresariais | Fonte autorizada, reconciliação e experimento conforme real_data_validation.md |
| P1 | Conectores Google/Meta/vendas/GA4 | Adapter API/OAuth, cofre, paginação/retry/incremental e execução real autorizada |
| P1 | Incerteza na fronteira/identificação fraca | Métodos e estudo de cobertura amplo; não deslocar percentis por conveniência |
| P1 | Priors/PPC/mistura nos motores nativos | Amostragem adequada e estudo controlado; smoke curto não certifica |
| P1 | Forecast Meridian/Robyn | Validar baseline, tendência, carryover e serialização no SDK nativo |
| P1 | Otimizadores externos | Horizonte, limites, totais e incerteza comprovados, sem fallback Ridge |
| P1 | CI Robyn e outros OS/runtimes | Provisionar R e validar; workflow Python manual ainda não executado remoto |
| P1 | Aplicação de treino/comparação | Estado, erros e autorização reais; HTML atual é painel Ridge exportável |
| P2 | Geo/hierarquias/reach/frequency/lift nativo | Novos contratos, dados e estudos científicos |
| P2 | Serviço público/filas duráveis | Destino autorizado, identidade, TLS, quotas, filas, backups e observabilidade |

Os controles locais não constituem uma oferta SaaS multiempresa. Serviço externo
continua fora do escopo escolhido pelo proprietário. Strix foi encerrado por decisão
expressa; não é uma dependência pendente desta entrega.
