# Validação integral e operacionalização

Fechamento local de 29–30/10/2026, com dados exclusivamente sintéticos. Este relatório
substitui os números históricos de 230 testes e 82,41% para o código atual.
Commit, publicação e merge seguem a aprovação das validações; os resultados remotos
da revisão publicada devem ser consultados na PR e no histórico de Actions.

## Resultado e escopo

| Verificação | Evidência local |
|---|---|
| Python próprio | 3.659/3.659 linhas e 1.316/1.316 branches, incluindo dois lançadores |
| JavaScript próprio | 792/792 linhas, 284/284 branches, 207/207 funções |
| Worker R | 102/102 expressões cobertas; 22/22 caminhos de decisões/laços |
| SDK MCP stdio | 45 ferramentas executadas, um template/recurso lido, três prompts renderizados |
| Motores | Ridge, Meridian, PyMC-Marketing e Robyn: treino, consulta, restauração e cenário |
| Futuro | Ridge e PyMC com plano explícito; operações indisponíveis retornam erro de capacidade |
| Formatos/perfis | Oito formatos normalizados com equivalência; 18 perfis de mídia |
| Segurança | Bandit sem achados; pip-audit/npm sem vulnerabilidades conhecidas na consulta; scanner de padrões sem achados |
| Mutação seletiva | Cinco alterações críticas detectadas após o baseline passar; não é escore exaustivo |
| Dependências R | 115 binários oficiais com URL/versão/SHA256 fixados; instalação em biblioteca nova verificada |

Recibos portáveis estão em [validation/closure](validation/closure/). As contagens
da suíte completa e os resultados externos são registrados no checklist desta revisão.

O denominador Python contém todos os módulos de produção e `server.py`/
`plugins/mmm-intelligence-local/launch.py`. Os 26 corpos declarativos de Protocol
seguem a exclusão padrão de ellipsis, revisada separadamente; nenhum módulo ou
tratamento de erro foi retirado. Todos os seis assets JS entram no denominador,
inclusive quando não carregados. R mede expressões/linhas com covr e decisões `if`
e corpo/saída de `for` por instrumentação AST; não é MC/DC nem cobertura de cada
operando de curto circuito ou de bibliotecas externas.

## Correções verificadas

- XLS real, Parquet escalar em lotes e XML tabular seguro, incluindo XSD local
  limitado, proteção de expansão, caminhos absolutos restritos e preservação de horário XLSX.
- Joins com prévia, cardinalidade declarada, agregação, alinhamento e bloqueio de
  duplicação de métricas; artefatos combinados alimentam Growth com linhagem transitiva.
- Materialização consumida pelos quatro motores, contratos de nomes/unidades e
  erros específicos de moeda/frequência. Não inventa exposição independente ou geografias.
- Tendências, segmentos, associações defasadas e mudanças de nível descritivas;
  coortes com acompanhamento completo e células pequenas suprimidas.
- Planejamento de poder, análise independente binária/Welch, SRM, perdas,
  guardrails e custos; vínculos entre plano, resultado e histórico imutável.
- Dashboard local sem login, com fluxos reais de importação, validação, joins,
  preparação, modelagem, coortes, experimentos, decisões, consulta e exportação.
  Corrigidos corte após 101 períodos, eixo de data declarado, seleção crossmedia
  e campo extra incompatível no exemplo de projeção futura.
- Robyn: gasto informado ao pacote é o total do período; o resultado simulado é
  `scenario_mean_response`, com gasto/carryover médios declarados. `response_total`
  continua sendo a série histórica por compatibilidade e é identificado como tal.
  Comparação nativa 1,1 contra 1,0 detecta mudanças de gasto e resposta.
- `MMMService` suporta `with`, fecha handlers e permite renomear o log no Windows,
  inclusive quando o chamador lança exceção.
- Três prompts MCP oficiais com IDs validados e sem execução automática.
  `optimize_budget` aceita backend explícito e recusa motores não suportados com
  `OPERATION_UNAVAILABLE`, sem substituição automática.

## Reproduzir

```powershell
.\.venv\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements/base-ci.txt
.\.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e '.[files,dev,audit]'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest --basetemp=var/tmp-repro -o cache_dir=var/cache-repro -q
.\.venv\Scripts\python.exe examples/operational_workflow.py --native --output-dir evidence/nova-verificacao
npm ci --ignore-scripts
npm run test:web
node tests/web/check_coverage.mjs
```

Para medir Python, crie diretórios de captura novos para cada execução. Execute
`python -m coverage run -m pytest -q` com `COVERAGE_FILE` apontando para um deles;
use `examples/coverage_gate.py record --directory DIRETORIO --label ROTULO`.
Habilite os três testes nativos com `MMM_TEST_NATIVE=1`; cada motor gera um
diretório exclusivo e manifesto. Repita a suíte em Windows e Linux para caminhos
específicos de sistema. O CI executa Windows/Linux/macOS × Python 3.11/3.12/3.13.

Combine somente manifestos da fonte executada compatível:

```powershell
python examples/coverage_gate.py check --manifest CAPTURA_WINDOWS/manifest.json --manifest CAPTURA_LINUX/manifest.json --manifest CAPTURA_NATIVA/manifest.json --output evidence/cobertura
```

Repita `--manifest` para o processo pai e os três motores. O gate valida os hashes
dos arquivos efetivamente executados, mantém todo o código atual no denominador
e exige igualdade exata de linhas e branches. Um snapshot de módulo não executado
não contribui cobertura nem impede reutilizar o worker inalterado. Fonte executada
alterada é recusada. Testes do próprio gate comprovam a recusa e o denominador.

O recibo Python preserva o hash dos bytes medidos e também o hash do blob Git.
No arquivo legado `rendering.py`, o checkout local usava CRLF e o Git conserva LF
conforme `.gitattributes`. A igualdade após essa única normalização e a igualdade
da AST compilada foram verificadas; não houve mudança de instruções ou exclusão.
Os outros 42 arquivos têm bytes idênticos. Após outro checkout, gere capturas novas;
o CI mede diretamente os arquivos dessa revisão e não reutiliza os dados locais.

Com R configurado, execute `examples/r_worker_coverage.R` e
`examples/r_worker_branches.R` com o caminho do projeto. Ambos falham abaixo de
100% no respectivo escopo. `examples/install_r_binaries.py` instala os arquivos
do manifesto fixado e verifica hashes antes de chamar R; não busca versões atuais
implicitamente. Cache/runtimes/bibliotecas ficam sob `var`, fora do Git.

O CI identificou uma resposta HTTP 429 no download oficial de R. O instalador
agora limita a dois downloads simultâneos e faz no máximo cinco tentativas para
falhas transitórias, com espera progressiva e `Retry-After` numérico limitado a
60 segundos. Erros permanentes, tamanho excessivo e divergência de SHA256
continuam encerrando a instalação. O cache recebe bytes somente após verificação,
por substituição atômica. Seis testes adicionais verificam recuperação, limite de
tentativas e recusa de conteúdo corrompido; um usa um servidor HTTP local real.
O download de um pacote oficial do manifesto também foi novamente verificado.

## Limites preservados

Nenhum dado real, API de mídia, alteração de campanha ou implantação externa foi
usado. O endpoint MCP HTTP continua autenticado; só o dashboard em loopback é
dispensado de autenticação manual. Aprovação humana nos registros não verifica identidade.

MCMC de 20 draws/tune, marcado `native_transport`, verifica IPC e persistência.
Validação analítica exige desenho adequado, no mínimo 1.000 draws para os motores
MCMC e avaliação de R-hat, ESS, divergências, sensibilidade e adequação preditiva.
Esse mínimo não certifica convergência. Robyn é busca regularizada, não MCMC;
busca curta não certifica estabilidade. Testes pareados/cluster não implementados
são recusados ou explicitamente limitados; não se simula identificação causal.
Otimização/futuro nativo sem contrato validado permanece indisponível.

Skills aplicadas: superpowers:test-driven-development e verification-before-completion.
Recursos executados: SDK MCP oficial instalado, GitHub MCP, Playwright/Chromium,
Docker local, coverage.py/pytest, Istanbul, covr, AST R, Ruff, mypy, Bandit,
pip-audit/npm e mutação seletiva. Referências usadas: código do SDK instalado,
documentação xlrd/Arrow/defusedxml/lxml e [código oficial Robyn](https://github.com/facebookexperimental/Robyn/blob/main/R/R/response.R).
