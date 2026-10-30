# Checklist de fechamento

Escopo: ingestão universal/Growth e operacionalização solicitados em 29/10/2026.
Base inicial medida: 230 testes, 82,411% de linhas e 71,933% de branches Python.
Relatório vigente: [operational-validation.md](operational-validation.md).

| Frente | Validação local |
|---|---|
| XLS/XLSX | Assinatura, abas, valores/datas/horários, dimensões reais, limites e conteúdo ativo testados |
| Parquet | Escalares/nulos, compressão, duplicação de nomes, arquivos externos e expansão/decodificação testados |
| XML | Caminhos relativos/absolutos restritos, atributos, hierarquia, XSD local limitado e XXE/DTD testados |
| Equivalência | Oito formatos passaram pelo mesmo pipeline com equivalência normalizada |
| Joins | Cardinalidade, agregação, alinhamento, contexto, perdas e prevenção de duplicação testados |
| Linhagem | SHA256, imutabilidade, fontes transitivas, reconsulta e substituição indevida testados |
| Materialização | Contratos consumidos por Ridge, Meridian, PyMC-Marketing e Robyn |
| Motores nativos | Treino, serialização, restauração, cenário e futuro suportado executados com dados sintéticos |
| Growth | Tendências/nível/defasagens descritivos, segmentos, coortes e censura testados |
| Experimentos | Poder, proporções/Welch, intervalos, SRM/perdas, guardrails/custos e vínculo plano→resultado testados |
| Aplicabilidade | 18 perfis, campos/datasets/destinos separados da qualidade, com recusa fundamentada |
| UI | Oito rotas Growth e dez rotas MMM; fluxos reais, erros, downloads, acessibilidade e viewports aprovados |
| Prompts | Três prompts oficiais descobertos/renderizados; IDs inválidos recusados; nenhum efeito automático |
| Recurso/STDIO | 45 ferramentas executadas, um template/recurso lido e persistência após reinício |
| Ambiente principal | `.venv` com files/dev/audit, fusos IANA e dependências complementares; pip check aprovado |
| Windows | Context manager fecha handlers e libera log mesmo com exceção do chamador |
| Python | 3.659/3.659 linhas e 1.316/1.316 branches; dois lançadores incluídos |
| JavaScript | 792/792 linhas, 284/284 branches e 207/207 funções |
| R | 102/102 expressões e 22/22 caminhos if/for; hashes do código registrados |
| CI | Matriz e três motores agregados; gates exatos Python/JS/R; ações fixadas e permissões de leitura |
| Segurança | Bandit, auditoria de dependências e scanner de padrões sem achados nas consultas locais |
| Mutação | Cinco mutações críticas detectadas; baseline passou; escopo seletivo explícito |
| Distribuição | Wheel/sdist/plugin reais, origem fora do checkout e igualdade dos arquivos do plugin testadas |
| Dependências R | 115 ZIPs oficiais com versões/URLs/SHA256 fixados e instalação real em biblioteca nova |

## Execuções observadas

- Windows no `.venv`: **657 aprovados, três nativos opcionais ignorados**, sem erros,
  em `var/reviewed-final-suite.log`.
- Linux local sem rede/portas: **653 aprovados, quatro ignorados**, sem erros,
  em `var/linux-operational.log`; inclui a exclusão do teste exclusivo Windows.
  Os três testes finais de procedência do gate também passaram no Linux, em
  `var/linux-provenance-reviewed.log`, usando o mesmo código de produção e o gate atual.
- Os três motores ignorados na suíte base foram executados nos ciclos nativos/MCP
  separados. Não são contabilizados como execução nativa a partir de skips.
- SDK: [recibo do protocolo](validation/closure/operational-protocol.json) e
  [ciclo universal](validation/closure/mcp-demo.json). Componentes concluídos foram
  retomados para acrescentar verificações de inventário/recursos/prompts e futuro PyMC;
  a retomada consta no recibo. Todos os modelos vieram de treinos nativos reais.
- Um aviso SciPy em teste de backtest permanece registrado; a execução passou e não
  é usado como certificação estatística. R emite avisos de locale/build e de busca curta.
- Revisão independente confirmou o gate Python/JS/R e apontou melhorias de procedência,
  contagem de laços, aliases e reprodutibilidade R, incorporadas e verificadas.

## Limites do aceite

100% refere-se ao código próprio medido. Não prova ausência de bugs, convergência,
causalidade, qualidade de dados empresariais ou adequação de investimento real.
Protocol/ellipsis, R/MC/DC e bibliotecas de terceiros têm o escopo descrito no relatório.
Estatística pareada/cluster, otimização/futuro nativo não suportado e integrações de
plataformas não são simulados. Nenhuma campanha, dado real ou serviço externo foi alterado.

Publicação/merge foram autorizados pelo proprietário somente depois das validações.
O estado remoto da revisão publicada deve ser lido na PR e em Actions; estes números
locais não são apresentados como execução remota.
