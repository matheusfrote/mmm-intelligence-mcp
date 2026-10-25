# Primeira entrega: execução e pendências

> Histórico da versão 0.1.0. A situação atual e a resolução das pendências estão em [extension-report.md](extension-report.md).

Verificação local em **24/10/2026**, no Windows, com Python **3.12.14**, SDK oficial MCP **1.30.0**, NumPy 2.5.4, SciPy 1.18.1 e Pydantic 2.14.1. Versões completas: [requirements-lock.txt](../requirements-lock.txt). O ambiente virtual e as instalações pertencem exclusivamente a este projeto.

## Funcionalidades prontas

| Etapa | Resultado e evidência |
|---|---|
| 1. Estrutura | Pacote instalável com pyproject, módulos separados, configuração por ambiente, README e documentos técnicos. Oito testes iniciais de contratos/persistência passaram. |
| 2. Ferramentas | As cinco ferramentas foram descobertas com inputSchema/outputSchema e executadas em subprocessos stdio reais, com o SDK oficial de cliente e servidor. |
| 3. Estatística | Adstock geométrico normalizado, Hill expoente 1, Ridge com sinais de mídia não negativos, controles livres, split temporal, MAE/WAPE/R², estado de carryover e simulação com horizonte 1–104. |
| 4. Qualidade e segurança | Ausências, datas duplicadas/irregulares, negativos, valores não finitos, dados não sintéticos, travessia de caminhos, junction Windows, hard links externos, corrupção e colisões concorrentes testados. Logs/erros estruturados; sem escrita em campanhas. |
| 5. Execução | Dependências instaladas; ciclo das cinco ferramentas concluído; consulta após reinício preservou exatamente o modelo. Testes, lint, formatação, integridade de dependências e build concluídos. |
| 6. Evolução | Contratos independentes para backends, otimização, dashboards e relatórios; todas as seis capacidades futuras marcadas como não implementadas. |

As rodadas ampliaram a verificação de 8 para 36, 47 e **48 testes**, sem falhas nas execuções concluídas. A instalação inicial foi bloqueada pela restrição de rede; o download posterior foi autorizado pela revisão automática e ocorreu na venv. A checagem de formatação apontou arquivos novos que precisavam padronização; eles foram formatados e os testes repetidos. Nenhum modelo foi ajustado em dados reais.

## Comandos e resultados finais

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check src tests examples server.py
.\.venv\Scripts\python.exe -m ruff format --check src tests examples server.py
.\.venv\Scripts\python.exe -m pytest --cov=mmm_intelligence --cov-report=term-missing --cov-report=json:evidence/coverage.json --junitxml=evidence/tests.xml -q
.\.venv\Scripts\python.exe -m build --no-isolation
```

- `pip check`: **No broken requirements found**.
- Ruff: **All checks passed**, **22 files already formatted**.
- Pytest: **48 passed in 12.21s**, zero falhas/skips nessa execução.
- Cobertura de linhas do processo principal: **89%** (503/566 statements). Os subprocessos stdio não são instrumentados por esta configuração; `server.py` aparece com 0% no relatório de cobertura, embora seus cinco handlers tenham sido exercitados pelos testes reais do protocolo. Não se interpreta cobertura como prova de validade estatística.
- Build: **wheel e sdist construídos**, com verificação da presença de código, testes, conftest, exemplos, documentação, lock e dataset sintético no sdist.
- Wheel instalado em `var/wheel-check` sem dependências adicionais; origem do import confirmada nessa pasta. Novo ciclo stdio completo com esse pacote instalado passou, inclusive reinício e leitura persistida. Usa as dependências da venv; não é prova de instalação offline em outra máquina.

Evidências: `evidence/tests.log` (registro histórico local: tests.log), `evidence/tests.xml` (registro histórico local: JUnit), `evidence/coverage.json` (registro histórico local: cobertura JSON), `evidence/build.log` (registro histórico local: build.log), `evidence/wheel-smoke.log` (registro histórico local: wheel-smoke.log) e `evidence/wheel-install/mcp-cycle.json` (registro histórico local: ciclo do wheel).

## Demonstração executada

Cliente: [examples/mcp_workflow.py](../examples/mcp_workflow.py), em transporte stdio, com descoberta, chamadas, validação JSON Schema de todas as saídas de sucesso e reinício do processo. Foram verificados também entrada inválida (`isError=true` do SDK), ausência (`NOT_FOUND`) e proteção contra sobrescrita (`ALREADY_EXISTS`).

Dataset de **156 semanas**, semente 42, de 02/01/2023 a 22/12/2025. Oito períodos iniciais de aquecimento, 116 linhas úteis de treino e 32 de teste. Treino termina em 12/05/2025; teste começa em 19/05/2025. Não houve reajuste nos dados de teste.

| Métrica | Treino | Teste | Benchmark de teste: média do treino |
|---|---:|---:|---:|
| MAE, receita fictícia | 99,7903 | 98,2440 | 723,4659 |
| WAPE (%) | 0,8130 | 0,8238 | 6,0666 |
| R² | 0,9614 | 0,9762 | -0,1852 |

Diagnósticos de treino: correlação residual lag 1 = -0,01633; posto = 9; número de condição = 106,564. Os coeficientes de mídia são não negativos. Isso descreve o exemplo sintético; não comprova atribuição causal, recuperação correta de canais ou eficácia comercial.

Simulação: **13 semanas**, orçamento total sintético **51.292,9552** tanto no comparador quanto no cenário, alocação **50% busca / 30% social / 20% vídeo**, controles mantidos nos últimos valores e carryover preservado.

| Resultado | Receita sintética prevista |
|---|---:|
| Referência: média dos últimos até 13 gastos por período | 160.834,5245 |
| Cenário 50/30/20 | 159.727,4443 |
| Diferença condicional | **-1.107,0802** |

Não há evidência de benefício dessa redistribuição no modelo demonstrativo. Não é recomendação operacional, lift causal, ROI realizado nem intervalo de incerteza. O gerador e o estimador compartilham uma família matemática, o que favorece as métricas preditivas.

Artefatos: `evidence/first-delivery/mcp-cycle.json` (registro histórico local: mensagens completas e modelo), `evidence/first-delivery/demo.csv` (registro histórico local: dataset CSV), `evidence/first-delivery/demo-dataset.json` (registro histórico local: dataset JSON com procedência). IDs usados nessa execução:

- dataset: `demo-7fb0255d26fd4a95a761d3c3926ae6ea`
- modelo: `model-35347aec93ac4acdbb8339d60c539da4`

Para consultar esse modelo localmente, configure `MMM_DATA_DIR` para a pasta absoluta `var/demo` deste projeto. Esses IDs não existem na raiz padrão `var`, que é outro armazenamento.

## Preservação e limites da inspeção

A pasta atual não é um repositório Git; não havia `.git` nem `AGENTS.md` aplicável encontrado nos diretórios examinados. Não houve commit, pull, push, publicação, deploy, instalação global de MCP ou alteração de configuração de contas. Todas as gravações desta implementação ficaram no novo diretório `mmm-intelligence-mcp`. Os cinco materiais originais em `F:\Marketing mix modeling` não foram editados.

Foi registrado um snapshot de hashes de **185 arquivos anteriores** do guia/laboratório, excluindo venv e caches. Na comparação final, **32 arquivos diferiam** do snapshot inicial. Este trabalho não os escreveu nem restaurou: preservou o estado presente e registrou hashes/horários em `evidence/preservation-check.json` (registro histórico local: preservation-check.json), comparável a [preservation-baseline.json](../preservation-baseline.json). A origem das mudanças paralelas não foi auditada; não se declara o guia inteiro inalterado nem se inclui essa revisão no escopo do servidor.

Foram usados como referências metodológicas o código/testes e as análises locais já existentes dos materiais; esta entrega não repete uma auditoria integral dos PDFs. O `server.py` anterior mencionado pelo pedido não pôde ser recuperado dos arquivos ou histórico acessíveis. A implementação entregue não depende desse protótipo ausente.

## Pendências declaradas

1. Google Meridian, Meta Robyn e PyMC-Marketing: **interfaces definidas, adaptadores/treinos não implementados**.
2. Otimização, dashboards e relatórios automatizados: **somente contratos**, sem produto operacional. O relatório desta entrega é documentação da verificação.
3. Incerteza, calibração experimental, identificação causal, comparação/sensibilidade de formas e validação em negócio real: ausentes.
4. Importador autorizado de dados reais, autenticação/multiusuário, cotas de CPU e transporte remoto: ausentes.
5. Python 3.11, outros sistemas operacionais e clientes de desktop específicos: não homologados; a execução real confirmada usa o cliente SDK em Windows/Python 3.12.
6. Migração para outra major do SDK, CI externa e publicação de pacotes: não realizadas.

Os detalhes de segurança e limites do isolamento estão em [security.md](security.md); critérios para cada integração futura em [roadmap.md](roadmap.md).
