# Auditoria de segurança e publicação — 0.3.1

Data de referência: 25/10/2026, America/Sao_Paulo. Após a descoberta do ambiente, o usuário definiu a entrega como **somente GitHub, sem deploy nesta etapa**. O escopo final é auditar, corrigir, testar e publicar o código no repositório existente. Deploy, domínio, TLS externo e smoke de produção não foram executados nem aprovados. Nenhum serviço, plano pago, campanha ou dado empresarial foi alterado.

## Ambiente e fronteiras de confiança

Repositório: [matheusfrote/mmm-intelligence-mcp](https://github.com/matheusfrote/mmm-intelligence-mcp), branch `main`, partindo do commit `4a4d5c226c892e9d9489c096cc930e9a0f2e6df2`. A árvore estava limpa no início. Não foram encontradas instruções AGENTS.md aplicáveis. O guia irmão foi preservado.

É um servidor Python 3.11+ com SDK MCP oficial, 16 ferramentas, stdio e HTTP opcional em **127.0.0.1**. O frontend consiste em HTML exportado, não um SaaS de cadastro/login. Dados são JSON imutáveis no sistema de arquivos; não há SQL, Supabase, Firebase, ORM ou migrations. Não existe integração de contas de anúncios. Meridian, PyMC-Marketing e Robyn são processos locais opcionais, com versões e formatos próprios.

| Fronteira / ativos | Ameaças consideradas | Controles e limites |
|---|---|---|
| Cliente → ferramentas MCP | Inputs inválidos, instruções como dados, abuso de cálculo | Pydantic, IDs e colunas validados, orçamento/linhas/tamanho limitados, semáforo de cálculo |
| HTTP → identidade / tenant | Spoofing, BOLA/IDOR, escalada reader → analyst | Bearer hash, papéis no backend, ContextVar e raiz separada por usuário, negativas reais |
| Modelo / dataset → armazenamento | Travessia, links, corrupção, sobrescrita | Raízes do host, rejeição de links/reparse points/hard links na leitura, hash e publicação exclusiva |
| Servidor → workers | Herança de credenciais, comandos indevidos, vazamento de erros, logs excessivos | Ambiente permitido explicitamente, argv fixo sem shell, erro público genérico, saída limitada a 1 MB, timeout e encerramento da árvore |
| Modelo → HTML / Markdown | XSS e requisições externas | JSON escapa `<`/`&`, DOM usa textContent, script autorizado por hash CSP; nomes de features restritos |
| Git / dependências → execução | Segredos, substituição de artefatos, tags mutáveis | Scanner de padrões/histórico, lock com hashes, wheels de dependências, actions por SHA e permissões contents:read |

Workers continuam executando com os privilégios do usuário do host: não são sandbox contra pacotes hostis. SHA-256 detecta corrupção, não autentica um administrador que possa reescrever o payload e o hash. ACL, integridade dos runtimes e confiança no operador fazem parte do modelo de ameaça.

## Achados, correções e regressões

Severidades abaixo consideram o serviço local autenticado. Nenhuma exploração externa ou exfiltração real foi alegada.

| ID / risco | Evidência e causa | Correção / verificação |
|---|---|---|
| SEC-01 / médio | Worker copiava todo os.environ, incluindo configurações HTTP e credenciais de serviços não relacionados | Allowlist de variáveis de SO/runtime/certificados; teste injeta três credenciais fabricadas, inclusive nome desconhecido, e confirma ausência. Recarga/cenário nativos exercitam o novo ambiente. Não impede leitura de arquivos permitida pelo SO. |
| SEC-02 / médio | Bridge repassava a mensagem de falha do worker, potencialmente com caminhos ou valores internos | Código BACKEND_FAILED e mensagem pública fixa; detalhes ficam em diagnóstico privado. Regressão com erro fabricado garante que valor e caminho não apareçam na resposta. |
| SEC-03 / médio | HTTP não limitava frequência nem requisições simultâneas; o semáforo só protegia cálculos | Janela móvel por usuário e bucket anônimo compartilhado; limite de concorrência por usuário, 429/Retry-After e contadores de chaves limitadas. Testes cobrem bloqueio, liberação e reset. Não é rate limit distribuído. |
| SEC-04 / baixo | Tokens estáticos não tinham campo de expiração/bloqueio; headers duplicados eram aceitos | expires_at com timezone e disabled opcionais; verificação em cada nova requisição; headers Authorization duplicados rejeitados; rotação após reinício testada. Configurações antigas continuam aceitas, inclusive sem expiração. |
| SEC-05 / baixo | Respostas HTTP não definiam no-store/headers defensivos; dashboard autorizava qualquer inline script | Headers em respostas normais e negativas; CSP do dashboard autoriza somente o hash do script gerado. Injeção deliberada no Chrome foi bloqueada; o cálculo legítimo continuou funcionando. A codificação anterior já impedia fechamento do script pelo payload. |
| SEC-06 / médio | CI usava versões resolvidas por ranges e actions por tags móveis | requirements/base-ci.txt universal com hashes, instalação limpa somente de wheels, projeto instalado sem resolver dependências/build isolado; actions oficiais por SHA, checkout sem credenciais persistidas e histórico completo. |
| SEC-07 / baixo | Configurações de usuário malformadas podiam gerar TypeError em vez de validação previsível | Validação explícita de tipos, chaves, nomes reservados e timestamps; configurações inválidas falham antes de servir HTTP. |
| SEC-08 / médio | stdout/stderr temporário do worker podia crescer até o término, embora o diagnóstico final já fosse limitado | Pipe drenado continuamente com cauda em memória/arquivo de até 1.000.000 bytes e indicação de truncamento. Teste produz 2 MB e verifica limite, cauda e ausência de bloqueio. |
| SEC-09 / baixo | Target/data aceitavam nomes irrestritos, diferentemente das mídias/controles, antes de entrar em bibliotecas externas | Todos os nomes declarados agora seguem identificador de até 64 caracteres; seis regressões bloqueiam caminhos, sintaxe de fórmula e tamanho excessivo antes de ler dados ou iniciar worker. Não se alega uma execução remota reproduzida no upstream. |

As regressões iniciais falharam antes das correções. A auditoria também introduziu mypy básico: foram corrigidos 11 erros de tipos, incluindo os nomes Python das anotações MCP, mantendo os aliases do protocolo. Não houve desativação de teste funcional ou alteração do motor para melhorar métricas artificiais.

## Autenticação, autorização e HTTP

Não há senha, cookie de sessão, recuperação de conta, callback OAuth ou endpoint administrativo. O transporte é stateless e autentica cada requisição por token opaco de alta entropia; SHA-256 armazena seu hash, não uma senha humana. Gere tokens com secrets.token_urlsafe(32), guarde-os fora do Git e configure somente hashes no host.

`MMM_USERS_JSON` aceita role/token_sha256 e, opcionalmente, `expires_at` ISO com timezone e `disabled` booleano. Exemplo estrutural em [operações](docs/operations.md), sem credencial utilizável. Para revogar, bloqueie/remova o usuário ou troque o hash e reinicie a instância. Expiração rejeita novas requisições; não cancela retroativamente um cálculo já autorizado. Não há refresh ou revogação distribuída.

Padrões: 120 requisições/minuto/usuário, 30 negativas anônimas/minuto por instância e quatro requisições simultâneas/usuário. São configuráveis pelo host, com limites de validação. O bucket anônimo não confia em X-Forwarded-For. Escalar réplicas multiplicaria os limites: um serviço externo exigiria controle compartilhado e quotas de disco.

O SDK já habilita proteção DNS rebinding por padrão. Ela foi preservada e testada: Host indevido 421; Origin externo 403. Não foi introduzido CORS permissivo. Sem token, expirado ou bloqueado: 401. Corpo maior que 4 MiB: 413. OPTIONS/PATCH/DELETE não suportados: 405. Headers incluem no-store, nosniff, DENY, no-referrer e CSP restritiva. HSTS não é anunciado sobre o HTTP local; não se alega HTTPS remoto.

## Arquivos, dados, logs e recuperação

Clientes fornecem IDs e dados inline, nunca caminhos de upload ou comandos. Não há fetch de URL controlada pelo cliente, SQL/eval ou shell: SQL injection e SSRF por esses vetores não se aplicam. Arquivos privados, modelos nativos, configurações pessoais, ambientes e logs não entram no Git ou no sdist. Não há endpoint para baixar logs.

Logs de eventos não copiam o payload nem o token. A saída nativa é privada e limitada, mas tracebacks podem conter dados/caminhos do job: proteja as raízes por ACL. Rotação dos eventos existe; retenção automática global dos datasets, backups e diagnósticos por usuário e quota agregada de disco não existem. Não importar dados pessoais por conveniência; o operador deve limitar o dataset a agregados autorizados e definir retenção/exclusão antes de uso real.

Foi executada cópia de uma raiz sintética parada, excluindo logs/jobs, para backup novo e restauração em outra raiz nova. Hashes dos arquivos coincidiram e a simulação retornou exatamente 95344,14042879624 antes/depois. Nada foi sobrescrito. Isso valida recuperação local por procedimento do operador, não backup gerenciado de nuvem. Uma falha de publicação injetada em teste deixou zero arquivos parciais e zero temporários pendentes.

## Inventário funcional e evidências

| Fluxo | Verificação |
|---|---|
| Dataset → validação → treino → consulta → simulação | Cliente oficial stdio, cinco ferramentas iniciais, erros estruturados e reinício |
| Importação, otimização, tuning, calibração, auditoria | Ciclo ampliado: 13 ferramentas locais e 16 descobertas; contratos/dados inválidos testados |
| Relatório / dashboard / CSV | Artefatos completos em [security031](docs/validation/security031); persistência imutável, métricas rastreáveis |
| Workers opcionais | Consulta, recarga nativa e cenário ×1,1 sobre os modelos sintéticos ajustados na auditoria 0.3; não é novo treino nem certificação MCMC |
| HTTP e tenants | Servidor loopback real, 401/403/413/421/429/405, reader sem escrita e usuário sem acesso a artefato de outro |
| Recursos / falhas | Timeout, árvore de processos, log de 2 MB truncado, concorrência, falha de disco/publicação e retorno sem detalhes internos |
| Navegador | Chrome real, desktop 1889 px e largura efetiva 500 px, sem overflow ou recursos externos; CSP bloqueou script não autorizado |
| Paridade UI/backend | Total 26000, horizonte 8, pesos 40/30/30: Python 95344,14042879624; navegador 95.344,14 |
| Desempenho proporcional | 20 tools/list sequenciais em loopback: p50 5,88 ms, p95 6,27 ms; não é capacidade de produção ou teste de carga externo |
| Backup / restauração | Novas pastas, hashes iguais, mesma previsão; origem preservada |

Somente dados sintéticos autorizados. Dados reais, causalidade e qualidade inferencial permanecem sujeitos aos limites da [auditoria científica](MMM_AUDIT_REPORT.md). Melhor segurança do transporte não melhora convergência ou identifica efeito de marketing.

## Scanners e cadeia de suprimentos

Instalação limpa em ambiente novo a partir de lock universal: 76 pacotes no Windows/Python 3.12, hashes obrigatórios, somente binários. Os snapshots anteriores permanecem históricos; o lock autoritativo do CI base agora é requirements/base-ci.txt. Nenhum pacote é instalado durante uma chamada MCP.

pip-audit 2.10.1 consultou os sete locks: principal (51 dependências), CI (76), Linux (41), Windows 3.11 (44), Meridian (75), PyMC (55) e Python do Robyn (17). Todos retornaram zero vulnerabilidades conhecidas. Contagens não são dependências únicas somadas. Não há auditoria completa de advisories R ou prova de ausência de pacote malicioso.

Bandit 1.9.4 inicialmente marcou seis itens de baixa severidade: três imports subprocess, duas execuções argv sem shell e o sentinela de token vazio. Revisão do fluxo confirmou runtimes fixos selecionados pelo host e rejeição do sentinela. Foram usadas exclusões **somente nessas linhas**, por ID, com justificativa adjacente; não há exclusão global de regra. O relatório final não contém achados ativos. Isso não significa que todos os comandos do SO fossem intrinsecamente seguros.

Mypy 1.20.2 verifica 20 módulos em modo básico, com imports externos sem stubs tolerados. Não é modo strict nem prova de tipagem completa das funções sem anotações. Pydantic e testes verificam contratos em execução. Ruff continua obrigatório.

`examples/check_secrets.py` verifica padrões reconhecidos no checkout publicável e nos blobs do histórico local, sem emitir o valor encontrado. A execução inicial revisou 110 arquivos/131 blobs e não encontrou padrões. Uma regressão com credencial fabricada somente no histórico confirmou detecção e ausência do valor na saída. O scanner não substitui revisão humana, perícia de entropia ou revogação se surgir exposição real.

## Ferramentas realmente utilizadas

Skills lidas/aplicadas: engineering-suite-review security-and-hardening e engineering-suite-ship entry-ship/shipping-and-launch. Terminal: Git, Python, uv, pytest, Ruff, mypy, Bandit e pip-audit. Documentação oficial MCP/pip/uv e OWASP foi consultada; código do SDK instalado também foi inspecionado.

MCPs: Chrome DevTools para visual/paridade/CSP; consultas de infraestrutura Vercel/Netlify retornaram nenhuma correspondência de projeto. Strix foi tentado após o usuário informar conexão, mas suas chamadas continuaram retornando solicitação de autenticação, sem dados de repositório ou resultado de scan. **Não foi realizado pentest Strix nem gasto crédito de scan.** Não se declara homologação por ferramenta que não concluiu a chamada. GitHub é utilizado para confirmar publicação e CI na seção de conclusão.

## Checklist de liberação e limites

| Critério | Estado / escopo |
|---|---|
| Nenhum achado crítico/alto conhecido sem mitigação | Aprovado no código/locks e ameaças locais examinados; não equivale a pentest externo |
| Segredos reconhecidos no código/histórico/artefatos | Nenhum encontrado nas verificações descritas; valores privados não publicados |
| Autenticação, papéis e isolamento | Aprovado nos testes negativos/positivos; bearer local, sem OAuth corporativo |
| Arquivos, integridade e recuperação | Aprovado no armazenamento local testado |
| Dependências / instalação limpa / lint / tipos / testes / build | Resultados finais registrados abaixo, com códigos de saída |
| Integrações nativas | Recarga/cenário reais; adequação estatística não certificada |
| Configuração de produção / domínio / TLS / firewall / monitoramento | Não aplicável à entrega GitHub; nenhuma produção configurada ou autorizada nesta etapa |
| Deploy e smoke externo | Não realizados por orientação explícita do usuário |

Para uma futura produção, são necessários destino e domínio autorizados, TLS/origins corretos, identidade/revogação apropriadas, armazenamento durável com ACL/backup/retention/quota, controle distribuído se houver réplicas, monitoramento e revisão de exposição. O código local não é declarado pronto para Internet por passar em testes.

Rollback desta publicação é um revert revisado, sem force push nem reescrita de história. Não há migração ou alteração de formato de dados nesta correção; não restaurar dados por cima de uma raiz existente. Antes de trocar uma instalação, preserve a raiz parada e valide a nova versão em raiz separada. Voltar a uma versão anterior pode reabrir os achados corrigidos e exige avaliação, não uma recomendação automática.

## Conclusão verificável

Suíte final local: **131 testes passaram em 20,31 s**, Python 3.12.14, no ambiente limpo com lock/hash, incluindo a regressão de YAML acrescentada após o primeiro CI. Um RuntimeWarning SciPy preexistente ocorreu em um solver nested; as saídas permaneceram finitas e a regressão passou. Ruff check/format passou; mypy básico passou nos 20 módulos; Bandit não apresentou achados ativos após as seis revisões de linha descritas; pip check não encontrou dependências quebradas. Wheel e sdist 0.3.1 foram construídos, incluindo este relatório, sem ambientes/modelos/logs privados.

A segunda busca de padrões revisou 112 arquivos/131 blobs, sem achados reconhecidos; as contagens são da execução, não constantes do projeto. O resumo publicável está em [security031-checks.json](docs/validation/security031-checks.json). Publicação, pacote instalado e CI são confirmados no registro posterior de progresso. O veredito se restringe ao servidor local e à publicação de código, sem deploy e sem validação de negócio real.

O [primeiro CI 40217269831](https://github.com/matheusfrote/mmm-intelligence-mcp/actions/runs/40217269831) não criou jobs por sintaxe YAML inválida no comando de instalação que contém `:all:`. A reprodução local com parser confirmou a causa. O comando foi colocado entre aspas, PyYAML tornou-se dependência dev explícita e um teste valida parsing e comandos escalares. O commit corretivo é `65f25710c1cdb3b37aa8d2a9a8ec23b821743f0e`; versões e hashes do lock permaneceram iguais. Essa falha não foi ocultada nem contada como teste de segurança aprovado.

**Publicação confirmada:** código em main, commits [5492c0d](https://github.com/matheusfrote/mmm-intelligence-mcp/commit/5492c0d811a164ca47eb8143715f228397467a25) e [65f2571](https://github.com/matheusfrote/mmm-intelligence-mcp/commit/65f25710c1cdb3b37aa8d2a9a8ec23b821743f0e), push normal e commit remoto consultado pelo GitHub MCP. O [CI corrigido 40217559233](https://github.com/matheusfrote/mmm-intelligence-mcp/actions/runs/40217559233) concluiu **10 jobs com sucesso**: 131 testes em cada uma das nove combinações OS/Python, além de instalação com hashes, lint, tipos, SAST, segredos, build, stdio, HTTP e stress; o décimo job auditou advisories. Os dez logs foram lidos; [snapshot](docs/validation/security031-github-ci.json). A atualização final deste relatório é um commit posterior de documentação. Nenhum deploy ou PyPI.

Referências primárias: [segurança/deploy do SDK MCP](https://py.sdk.modelcontextprotocol.io/run/deploy/), [OWASP MCP](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html), [instalações seguras pip](https://pip.pypa.io/en/stable/topics/secure-installs/), [locks e hashes uv](https://docs.astral.sh/uv/pip/compile/).
