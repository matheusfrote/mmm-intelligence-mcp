# Segurança e escopo 0.2

Somente dados sintéticos foram usados. Não há integração de contas de anúncios, modificação de campanhas, compras de mídia, publicação de pacotes ou deploy. Pacotes Python, R portátil e bibliotecas R ficaram em diretórios deste projeto, sem Registro/PATH global. Dependências e imagens de teste foram baixadas dos distribuidores; isso não constitui um serviço externo implantado.

## Arquivos e origem

Clientes fornecem IDs e linhas inline, nunca caminhos. Artefatos ficam sob MMM_DATA_DIR em datasets, models, backend_models, dashboards e reports. Logs ficam em logs; jobs privados temporários ficam em jobs. O R usa também um diretório privado automaticamente limpo na raiz temporária autorizada do SO, para evitar espaços incompatíveis com seu tempdir no Windows.

A raiz é decisão do host. IDs bloqueiam travessia, caminhos absolutos/UNC, streams alternativos e nomes reservados. Symlinks, junctions e reparse points são rejeitados; leitura rejeita hard links múltiplos. Escritas são publicadas de forma atômica sem substituir destino. Há limites de tamanho/linhas e hash de integridade. Modelos usam JSON com formatos nativos Protobuf, NetCDF ou JSON oficial em base64, sem pickle/RDS.

SHA-256 não é assinatura. Um administrador que possa alterar o payload e recalcular o hash continua sendo parte da fronteira de confiança. O cliente não fornece modelos nativos arbitrários nem registries/código de backend. Logs nativos privados podem conter tracebacks e caminhos; não publique diagnósticos empresariais.

MMM_ALLOW_REAL_DATA=false bloqueia artefatos não declarados sintéticos. import_dataset exige procedência, referência de autorização e schema válido; para dados reais, o operador também precisa habilitar o flag. Nenhum dado real foi importado. A declaração sintética é confiada ao operador, sem perícia automática da origem.

## HTTP, papéis e isolamento

Stdio continua padrão. HTTP é opcional, autenticado e limitado a 127.0.0.1. O host configura hashes SHA-256 de tokens bearer fortes; comparações usam tempo constante. Usuários possuem tokens distintos, papel analyst/reader e diretório individual. Chamadas sem token recebem 401; reader não escreve; um usuário não encontra artefatos de outro. Tokens não são registrados pelos eventos da aplicação. Não há compartilhamento implícito entre contas.

É autenticação estática local, não um provedor OAuth federado, ambiente de produção multi-host ou isolamento de código hostil. Não há endpoint público, túnel, TLS remoto ou integração com identidade corporativa nesta entrega. Não coloque segredos na configuração versionada. Reinicie a instância para mudar os usuários.

## Recursos e processos

O servidor configura BLAS/OMP antes de carregar NumPy. Cálculos têm um slot por instância e recusam concorrência com BUSY. Workers de backend são subprocessos fixos, sem shell, com timeout. No Windows, Job Object limita CPU/memória e encerra todos os descendentes ao fechar, inclusive R; falha na configuração impede o cálculo. Em POSIX há timeout e encerramento do grupo de processos, sem configuração automática de cgroups.

Isso não é uma sandbox do SO. Bibliotecas precisam ler código/runtime fora da raiz; outro processo com privilégios para substituir diretórios concorrentemente pode disputar verificações e abertura. Proteja as raízes por ACL, não use pastas compartilhadas e isole contas/processos antes de expor serviços fora do computador. A aplicação não altera configurações globais de energia, CPU ou sistema.

## Evidências

Testes verificam travessia, link externo, junction Windows, escrita concorrente, corrupção, origem dos dados, papéis, usuários, timeout e execução limitada. O teste HTTP usa uma conexão loopback real e encerra o servidor. Os motores foram exercitados com dados sintéticos e formatos oficiais; isso verifica engenharia, não identificação causal ou homologação empresarial.

A matriz de CI não publica pacotes ou implanta serviços. O usuário autorizou publicar o código em repositório público; dados empresariais, identidade corporativa e serviço externo continuam exigindo escopo e ambiente definidos. `.gitignore` e `MANIFEST.in` excluem logs/evidências privadas, modelos, venvs, arquivos de credenciais, configurações locais e o inventário de preservação. Um teste constrói wheel e sdist e inspeciona efetivamente seu conteúdo. A auditoria de versões Python está em `validation/dependency-audit.json`; não equivale a prova de ausência de vulnerabilidades ou auditoria de todo o ecossistema R.
