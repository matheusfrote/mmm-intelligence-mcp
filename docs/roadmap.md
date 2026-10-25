# Evolução planejada: interfaces, sem integrações executáveis

> Documento histórico do planejamento 0.1. Na versão 0.2, as seis capacidades abaixo foram implementadas e receberam testes locais. Consulte [extension-report.md](extension-report.md) e [operations.md](operations.md) para situação atual, limites dos motores e evidências. Os trechos seguintes registram os critérios originais, não o status atual.

O pacote `integrations/contracts.py` define contratos independentes de frameworks e de MCP: `ModelingData`, `ModelBundle`, `Scenario`, `ModelBackend`, `BudgetConstraints`, `InvestmentOptimizer`, `DashboardRenderer` e `ReportRenderer`. O registro `PLANNED_CAPABILITIES` marca as seis áreas como `planned_not_implemented`.

Esses contratos não são adaptadores funcionais nem um mecanismo de seleção de backend. O serviço atual chama o motor Ridge local. Nenhuma biblioteca Meridian/Robyn/PyMC foi instalada para este projeto, nenhum mock é apresentado como resultado desses motores e nenhum import opcional ocorre em startup.

| Área | Implementação futura | Critério antes de declarar pronta |
|---|---|---|
| Google Meridian | Adaptar contrato a dados e modelo do SDK oficial escolhido; ambiente isolado | Instalar versão suportada, ajuste/diagnósticos reais, persistência e integração MCP testados |
| Meta Robyn | Bridge explícita Python/R ou processo separado com contrato serializado | R/Robyn instalados, execução completa e tradução de unidades/parâmetros comprovadas |
| PyMC-Marketing | Adaptar features, priors, amostragem e posterior | Fit real, diagnóstico de convergência e previsão posterior testados |
| Otimização | Consumir backend, horizonte, estado e restrições independentes | Verificar conservação/limites, casos inviáveis e comparação com malha independente |
| Dashboards | Consumir bundle versionado e resultados de cenário | Renderização e testes de dados completos, sem mascarar ressalvas |
| Relatórios automatizados | Renderer local separado da operação MCP | Artefato real, métricas reconciliadas, proveniência e conteúdo conferidos |

Antes de permitir importação real: definir formato e schema, controles de acesso, consentimento, validação de origem e política de retenção. Antes de recomendar investimentos: identificação causal, calibração, incerteza, sensibilidade de formas, suporte observado e restrições de negócio. Antes de distribuir para outros ambientes: CI em Python 3.11/3.12+, testes por sistema operacional e locks apropriados. Antes de migrar o SDK MCP para outra major: adaptar APIs e repetir descoberta, execução, falhas e reinício do processo.

Não há prazos ou automações agendadas. Qualquer acesso a contas, publicação ou serviço externo exige um novo escopo autorizado.
