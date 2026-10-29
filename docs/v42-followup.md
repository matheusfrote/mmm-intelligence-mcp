# Continuação V4.2 — validações de 28/10/2026

Registro consolidado em 29/10/2026. Código publicado em `feat/v4-intelligence`,
sem merge na main, release, PyPI ou implantação externa. O dashboard abre
diretamente no workspace local; `/mcp` mantém autenticação. Dados de teste sintéticos.

## Correções concluídas

- A verificação do wheel compara caminhos reais: no macOS, `/var` e `/private/var`
  podem identificar a mesma pasta. O verificador canonicaliza seu próprio diretório
  temporário antes de iniciar o MCP. O armazenamento continua rejeitando links e
  reparse points; nenhum controle de acesso foi removido.
- Falhas dos subprocessos de verificação agora incluem o trecho final do diagnóstico.
- O E2E aguarda a renderização da rota, além da mudança do hash. Isso corrige a
  corrida que selecionava checkboxes da tela anterior nos runners do GitHub.
- Novo workflow testa o dashboard em Chromium e a imagem Docker real. Actions e
  imagem base estão fixadas por SHA/digest.
- Instalação documentada aponta explicitamente para a branch publicada da V4.2.

## Evidência executada

Commit de código verificado:
[`c5f8eaa`](https://github.com/matheusfrote/mmm-intelligence-mcp/commit/c5f8eaa4b5072e8e459bdf27010c3dbab015ec40).

| Verificação | Resultado e alcance |
|---|---|
| Python local | 198 testes aprovados, cobertura 81,50%, um aviso SciPy preexistente |
| Qualidade local | Ruff, formatação do código, mypy em 32 módulos, Bandit e scanner de padrões de segredo aprovados |
| [CI base](https://github.com/matheusfrote/mmm-intelligence-mcp/actions/runs/40709406231) | Nove combinações Windows/Linux/macOS × Python 3.11/3.12/3.13 e segurança aprovadas; inclui wheel instalado, ciclo MCP, HTTP e stress sintético |
| [CI dashboard/contêiner](https://github.com/matheusfrote/mmm-intelligence-mcp/actions/runs/40709406223) | Chromium e Docker em Linux aprovados |
| Browser local | Cenário E2E Chrome, 24 chamadas MCP, cinco larguras e axe na visão geral em dois temas |
| Docker local | UID 10001, raiz somente leitura, sem rede em execução/portas publicadas, 26 ferramentas, 401 sem bearer, 403 para origem externa, isolamento do workspace e persistência após recriação |
| Wheel com alias | Venv nova fora da fonte, origem da importação e console verificados, 26 ferramentas, 23 chamadas e recarga aprovados |
| uvx 0.12.12 / pipx 1.18.7 | Wheel instalado em ambientes isolados Windows/Python 3.12.14; doctor, 26 ferramentas, 23 chamadas e recarga aprovados em cada ambiente |

Os gerenciadores resolveram NumPy 2.5.4 e SciPy 1.18.1; a instalação com lock manteve
NumPy 2.4.6 e SciPy 1.17.1. Isso não certifica todas as versões possíveis nem os
runtimes opcionais. Cache/home/bin de teste ficaram em `var`; o PATH global não
foi alterado. A primeira tentativa pipx foi interrompida e não é contabilizada;
o recibo identifica a nova execução completa.

Recibos revisados: [CI](validation/v42-followup/github-ci.json),
[Docker](validation/v42-followup/container-local.json),
[wheel](validation/v42-followup/wheel-alias.json) e
[uvx/pipx](validation/v42-followup/isolated-launchers.json).
As falhas dos runs 40578382063 e 40708283130/40708283398 permanecem no histórico;
os runs aprovados acima validam as correções.

## Pendências preservadas

O [roadmap](roadmap.md) registra extensões ainda não implementadas: forecast
Meridian/Robyn, otimizadores nativos, adapters de coleta real, CI dos motores
opcionais e estudos científicos mais amplos. A validação empresarial depende
de dados/experimentos autorizados; os testes sintéticos não demonstram causalidade.

O plugin local foi empacotado e testado por protocolo, mas não instalado/avaliado
em um host de plugins. Diretório público, OAuth, HTTPS público, políticas e identidade
do publicador não foram entregues. Docker local não certifica TLS, scan completo
do sistema operacional da imagem ou operação em produção. A decisão de manter
a distribuição no GitHub e encerrar sem Strix continua respeitada.
