# Entrega 0.2 — resolução das pendências

> Registro da etapa local anterior à publicação. O status de GitHub, correções adicionais, CI e testes atuais está em [IMPLEMENTATION_PROGRESS.md](../IMPLEMENTATION_PROGRESS.md). Arquivos brutos de evidência permanecem locais; as cópias públicas revisadas estão em [validation](validation/README.md).

Trabalho local em 24/10/2026. Este relatório substitui o status de pendências do relatório 0.1, preservado como histórico. As verificações abaixo usam dados sintéticos; não equivalem a validação empresarial ou identificação causal.

## Implementado e executado

| Pendência anterior | Resultado atual | Evidência |
|---|---|---|
| Google Meridian | Adaptador real 2.1.0, treino, holdout, Protobuf oficial, recarga e cenário histórico em novo processo MCP | [ciclo MCP](validation/meridian-mcp.json) |
| PyMC-Marketing | Adaptador real 1.3.0, posterior, NetCDF, previsões na unidade original, recarga e cenário MCP | [ciclo MCP](validation/pymc-mcp.json), [diagnósticos nativos](validation/pymc-diagnostics.json) |
| Meta Robyn | R portátil 4.5.2, pacote Robyn 3.12.1, Nevergrad isolado, treino real, JSON oficial, reconstrução e cenário nativo | [ciclo MCP](validation/robyn-mcp.json), [pacotes R](../requirements/robyn-r-packages.csv) |
| Otimização | SLSQP com gradiente analítico, total fixo, limites, detecção de inviabilidade e comparação com malha independente | tests/test_advanced.py e [ciclo ampliado](validation/mcp-cycle.json) |
| Dashboards | HTML independente, histórico/holdout, coeficientes e simulação interativa local | [dashboard executado](validation/dashboard.html) |
| Relatórios | Markdown gerado a partir das métricas/coeficientes/procedência persistidos | [relatório gerado](validation/report.md) |
| Incerteza | Bootstrap de resíduos em blocos e intervalos pareados da média condicional | Testes de reprodução, orçamento e cenário idêntico |
| Calibração | Reponderação por lift/erro padrão declarado; origem, ESS e suporte explícitos | Teste sintético; sem certificação experimental |
| Sensibilidade/seleção de formas | Grid temporal interno anterior ao teste externo, rankings persistidos | Teste altera o futuro externo e exige mesmo ranking |
| Importação | Linhas inline, procedência e autorização explícitas, validação antes de persistir | Dados não sintéticos bloqueados por padrão |
| Autenticação/multiusuário | HTTP loopback com bearer, analyst/reader, hashes e raiz por usuário | `evidence/http-functional/result.json` (registro histórico local: conexão HTTP real), testes ASGI |
| Cotas/processos | Uma thread numérica, um cálculo por instância, timeout, árvore de processos e Job Object Windows com CPU/memória | Testes de execução/timeout e workers nativos reais |
| Python 3.11 | Runtime 3.11.16 instalado dentro do projeto, sem Registro/PATH | `evidence/python311-final-tests.log` (registro histórico local: suíte 3.11) |
| Linux | Contêiner local descartável, 1 CPU/2 GB, dependências Linux resolvidas separadamente | `evidence/linux-final-tests.log` (registro histórico local: suíte Linux), [lock Linux](../requirements/base-linux-py312.txt) |
| SDK MCP | Migração real para 2.3.0; 15 ferramentas descobertas e clientes stdio/HTTP executados | Scripts e testes de protocolo |
| CI e distribuição | Matriz Windows/Linux/macOS, wheel/sdist locais e locks dos ambientes | .github/workflows/ci.yml, dist e requirements |

Os renderers atuais consomem modelos do motor local. Resultados dos motores externos são consultados/armazenados como JSON estruturado, com formatos nativos íntegros no armazenamento interno. A interface externa não promete uma previsão futura universal: Meridian opera cenários nas dimensões históricas e Robyn expõe resposta por canal. Isso é documentado, sem substituir silenciosamente os motores pelo Ridge.

## Verificações de software

- Windows/Python 3.12.14: **64 testes passaram**; log/JUnit/cobertura em evidence/v2-final-tests.log, evidence/v2-tests.xml e evidence/v2-coverage.json.
- Windows/Python 3.11.16: **64 testes passaram**, em `evidence/python311-final-tests.log` (registro histórico local: python311-final-tests.log).
- Linux/Python 3.12 no contêiner: **64 testes passaram**, sem warnings na execução final; `evidence/linux-final-tests.log` (registro histórico local: linux-final-tests.log) e `pip check` confirmam o resultado.
- Ruff/lint, formatação, integridade de dependências e build local são repetidos antes da entrega final.
- Os testes rápidos não importam TensorFlow/PyMC/R na venv principal. Os três ciclos nativos MCP são evidências adicionais reais, separadas da contagem de unitários/integração base.
- A cobertura do processo principal não instrumenta workers de outros ambientes nem todos os subprocessos stdio; não representa cobertura estatística ou causal.
- O wheel 0.2 foi instalado em diretório separado, com ciclo estendido/reinício reais; todos os módulos e o worker R no wheel final são comparados byte a byte com as fontes verificadas. O pacote fonte inclui documentação, exemplos, testes, locks e matriz de CI.

O dashboard foi aberto em navegador de contexto isolado: duas linhas de observado/previsto, três sliders, previsão atualizada ao mudar orçamento de 161.400,634 para 143.856,28 no cenário testado, e zero recursos externos. O gráfico foi inspecionado visualmente. Não foi publicado.

HTTP: foi iniciado um servidor loopback com tokens efêmeros e realizado acesso pelo cliente SDK 2. O teste comprovou 401 sem token, criação por analyst, invisibilidade de artefatos entre usuários e bloqueio de escrita para reader. O processo foi encerrado ao final; nenhum listener público ou túnel foi criado.

Docker estava desligado no início. Foi iniciado temporariamente para o teste Linux, com contêiner removido automaticamente, e parado após a verificação para restaurar o estado anterior. Não foram alterados planos de energia nem configurações globais do Python, R ou MCP.

## Resultados estatísticos: engenharia não é certificação

Métricas abaixo correspondem a testes sintéticos curtos dos adaptadores, e não a uma comparação de qualidade entre frameworks. O modelo local e os motores possuem especificações, priors, transformações e janelas distintas; o Robyn aplica sua própria janela e arredondamento temporal.

| Motor/ciclo | MAE | WAPE (%) | R² | Volume |
|---|---:|---:|---:|---|
| Ridge local | 98,244 | 0,824 | 0,976 | Split temporal, sem reajuste no teste |
| Meridian smoke | 1.632,963 | 13,693 | -3,919 | 2 chains, 50 draws |
| PyMC smoke | 418,136 | 3,506 | 0,677 | 2 chains, 50 draws |
| Robyn smoke | 338,962 | 2,837 | 0,757 | 1 trial, 200 iterações |

O smoke Meridian apresentou R-hat máximo 2,89 e ESS mínimo 3: **não é um ajuste convergido utilizável para decisão**. PyMC com 100 draws/100 tune apresentou R-hat máximo 1,145 e ESS bulk mínimo 12,09: também insuficiente para certificar inferência. A versão registra esses diagnósticos, sem trocar sinais ruins por status verde. Execuções adicionais com maior volume são registradas separadamente quando concluídas.

Foram concluídas execuções ampliadas com **4 cadeias, 1.000 passos de ajuste e 500 draws por cadeia**, preservando novos IDs e sem substituir os smokes:

| Motor ampliado | MAE | WAPE (%) | R² | R-hat máximo | ESS bulk mínimo |
|---|---:|---:|---:|---:|---:|
| Meridian | 1.730,526 | 14,511 | -4,225 | 1,01 (resumo arredondado nativo) | 656 |
| PyMC | 425,584 | 3,569 | 0,671 | 1,014903 | 312,238 |

Evidências: [Meridian ampliado](validation/meridian-extended.json) e [PyMC ampliado](validation/pymc-extended.json). O PyMC teve zero divergências. Mais amostras melhoraram a mistura das cadeias, mas **não corrigiram automaticamente a especificação ou o desempenho de holdout**. O resultado ruim do Meridian permanece exposto; R-hat melhor não torna o modelo adequado ao caso. Não se certifica convergência ou validade de negócio por esses números isolados. O motor local contém tendência/sazonalidade explícitas; os adaptadores usam suas especificações nativas declaradas e não foram selecionados para reproduzir a verdade do gerador.

Os modelos ampliados usam limite de artefato de 50 MiB configurado pelo operador durante a execução: o NetCDF PyMC ampliado embutido ocupa aproximadamente 23,5 MiB. Para consultar esses IDs, use o mesmo limite via `MMM_MAX_FILE_BYTES=52428800`; o padrão 10 MiB continua preservado e não é ignorado silenciosamente.

Nenhum limiar de R-hat, R² ou WAPE comprova causalidade. O gerador é construído e compartilha família matemática com o motor local; bom desempenho do laboratório não identifica contribuições empresariais. Calibração sintética testa o mecanismo de software, sem provar randomização ou transportabilidade de experimento real.

O [ciclo local final](validation/mcp-cycle.json) descobriu as 15 ferramentas e executou as 12 ferramentas locais, incluindo importação inline e status. Os três endpoints nativos foram exercitados pelos ciclos MCP de cada motor. O [dashboard final](validation/dashboard.html), [relatório final](validation/report.md) e [dataset final](../examples/demo.csv) estão exportados sem servidor externo.

## Falhas encontradas e corrigidas

1. PyTensor tentou usar cache externo ao projeto: flags de cache/compilação foram direcionadas aos jobs privados.
2. O target PyMC foi inicialmente extraído em escala padronizada: o adaptador agora registra/solicita `y_original_scale`. A evidência antiga `evidence/pymc-functional.json` (registro histórico local: pymc-functional.json) registra o problema e foi **superada** por `evidence/pymc-functional-v2.json` (registro histórico local: pymc-functional-v2.json) e pelo ciclo MCP atual.
3. R recusou tempdir com espaços: usa temporário privado autorizado do SO, com remoção automática.
4. Robyn 3.12.1 falhou em modo quiet por variável interna `pb`: o adaptador usa o caminho normal com progresso redirecionado ao log privado, sem alterar o pacote upstream.
5. JSON R pode desencaixotar um vetor de aviso de um elemento: o worker normaliza warnings para lista antes do envelope.
6. A inicialização simultânea de vários processos com BLAS sem limite provocou erro de memória: o pacote limita as threads antes de importar NumPy; a aceitação passou com execução sequencial e workers limitados.
7. Cache pytest Windows no bind Linux produziu um warning: a execução final usa cache temporário no contêiner e passou sem avisos.
8. A revisão automática de aprovação falhou temporariamente por limite de uso ao baixar R. Após confirmação de uso normal, a mesma ação passou pela revisão e foi executada; nenhum controle foi contornado.
9. O parser padrão de datas Python também aceita ISO de semana: a validação agora exige explicitamente YYYY-MM-DD e possui regressão para não aceitar esse formato fora do contrato.

Falhas/artefatos antigos foram preservados como evidência, sem sobrescrever datasets/modelos. Os caminhos de evidência finais acima distinguem execuções bem-sucedidas dos diagnósticos de tentativa.

## Limites que exigem outro tipo de evidência ou autorização

O trabalho de implementação local está entregue. Os itens abaixo não podem ser declarados prontos somente com código/testes sintéticos:

1. **Validação em negócio, identificação causal e calibração experimental real:** dependem de dataset autorizado, definição do KPI/estimando, contexto de negócio, desenho causal e experimento válido. Nada disso foi inventado ou coletado sem autorização.
2. **Homologação macOS, Python 3.13 e clientes de desktop específicos:** há matriz/artefatos configurados, mas os ambientes não foram executados nesta máquina. Windows 3.11/3.12 e Linux 3.12 têm evidência local real.
3. **CI externa, publicação de pacote/repositório ou deploy:** arquivos e pacotes estão preparados, mas não foram enviados a contas/serviços. A restrição original de não publicar sem autorização foi preservada; é necessário indicar destino e aprovar a ação concreta.
4. **Serviço corporativo público:** HTTP fornecido é privado/loopback, com credenciais estáticas. Identidade corporativa, TLS remoto, cgroups POSIX, filas distribuídas e garantias multi-host exigem infraestrutura e revisão específicas, não foram apresentados como produto implantado.

Esses limites não são integrações fictícias ou funções vazias: são fronteiras explícitas da evidência disponível. A fonte de verdade para cada execução é seu log/JSON, não a existência de um arquivo de configuração.
