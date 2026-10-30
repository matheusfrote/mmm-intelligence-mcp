# Decisão de licença

O proprietário autorizou **Apache-2.0** nesta execução, com copyright **2026 Matheus Frote**.
O texto integral está em [LICENSE](../LICENSE), com [NOTICE](../NOTICE) e metadados SPDX no pyproject. A tabela registra a avaliação anterior à decisão.

| Opção | Consequências principais |
|---|---|
| MIT | Texto curto, uso comercial permitido, preservação de copyright/licença; não traz concessão de patentes expressa equivalente à Apache |
| Apache-2.0 | Permissiva, concessão expressa de patentes dos contribuidores, preservação de avisos/licença, registro de arquivos modificados e NOTICE quando aplicável |

Recomenda-se Apache-2.0 pela clareza para contribuições e integrações. A licença do
projeto não relicencia dependências: preservar suas licenças e avisos ao redistribuí-las.
Wheel contém código do projeto, não runtimes nativos; ambientes R e suas dependências
podem ter obrigações distintas, inclusive GPL. Não empacotar esses ambientes como se
todos estivessem sob a licença do projeto. Inventário dos metadados instalados será
registrado separadamente; não equivale a parecer jurídico de toda distribuição futura.

Fontes consultadas em 26/10/2026: [MIT](https://opensource.org/license/mit),
[Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0).

LICENSE/NOTICE integram wheel e sdist e têm verificação automatizada. O [inventário de metadados](validation/v4/licenses.json) registra dependências diretas e principais frameworks instalados, não uma auditoria de todas as dependências transitivas. NumPy declara múltiplas licenças permissivas; SciPy informa BSD; MCP/Pydantic/Nevergrad e Robyn informam MIT; PyMC/ArviZ/PyMC-Marketing indicam Apache. Metadados sem expressão curta são preservados como ausentes, sem inferir a licença. Consulte os arquivos upstream antes de redistribuir ambientes completos. R e suas dependências conservam obrigações próprias. Publicação de release ou PyPI continua sendo uma ação separada.
