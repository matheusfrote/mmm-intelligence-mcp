# Estado da entrega e evolução planejada

Atualizado em 29/10/2026. [Entrega V4](v4-delivery.md), [dashboard V4.2](v42-delivery.md)
e [continuação com CI observado](v42-followup.md) registram etapas distintas.
Não há prazos ou automações agendadas.

## Entregas verificadas

| Item | Estado |
|---|---|
| Publicação do código | Branch `feat/v4-intelligence` no GitHub; main preservada |
| CI da base V4.2 | Nove combinações OS/Python e segurança aprovadas no commit c5f8eaa |
| Dashboard de treino/comparação | Dez módulos, ações MCP reais, sem login local; E2E Chrome local e Chromium no CI aprovados |
| Contêiner | Construção, isolamento e persistência após recriação verificados localmente e no CI; imagem fixada por digest |
| Distribuição local | Wheel/sdist, CLI, ZIP do plugin e instalação isolada uvx/pipx verificados no alcance documentado |

## Trabalho futuro

| Prioridade | Pendência | Dependência e aceite |
|---|---|---|
| P0 | Release/PyPI | Publicação separada do push; escopo de publicação e conta/Trusted Publisher apropriados |
| P0 | Proteger main | Aprovação das regras, revisão viável para mantenedor solo e nomes reais dos checks |
| P0 | Validar decisões empresariais | Fonte autorizada, reconciliação e experimento conforme real_data_validation.md |
| P1 | Conectores Google/Meta/vendas/GA4 | Adapter API/OAuth, cofre, paginação/retry/incremental e execução real autorizada |
| P1 | Incerteza na fronteira/identificação fraca | Métodos e estudo de cobertura amplo; não deslocar percentis por conveniência |
| P1 | Priors/PPC/mistura nos motores nativos | Amostragem adequada e estudo controlado; smoke curto não certifica |
| P1 | Forecast Meridian/Robyn | Validar baseline, tendência, carryover e serialização no SDK nativo |
| P1 | Otimizadores externos | Horizonte, limites, totais e incerteza comprovados, sem fallback Ridge |
| P1 | CI dos motores nativos | Executar workflows PyMC/Meridian; provisionar e testar R/Robyn; a matriz base não os certifica |
| P2 | Plugin no cliente desktop | Instalação e avaliação no host; teste stdio não substitui essa validação |
| P2 | Plugin público | HTTPS/OAuth, políticas publicadas, identidade, países e avaliação do diretório |
| P2 | Qualificação de produção da imagem | Scan de SO, nginx/TLS e backup/restauração no destino; smoke Docker não substitui esses checks |
| P2 | Geo/hierarquias/reach/frequency/lift nativo | Novos contratos, dados e estudos científicos |
| P2 | Serviço público/filas duráveis | Destino autorizado, identidade, TLS, quotas, filas, backups e observabilidade |

Os controles locais não constituem uma oferta SaaS multiempresa. Serviço externo
continua fora do escopo escolhido pelo proprietário. Strix foi encerrado por decisão
expressa; não é uma dependência pendente desta entrega.
