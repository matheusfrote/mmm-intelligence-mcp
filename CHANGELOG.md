# Changelog

## 0.4.0 — preparada localmente, sem release publicada

- Apache-2.0 autorizada; NOTICE, contribuição, conduta, segurança, templates e Dependabot.
- CLI doctor/config e exclusão unitária pelo operador com hash, limites do host e referências verificadas.
- Dez ferramentas adicionais: CSV, qualidade, análise canônica, comparação, capacidades, projeção, exportação, inventário, retenção e estado de fontes.
- CSV sem limpeza silenciosa, preservando original, hash, mapeamento, fuso e políticas de agregação.
- Projeção futura nativa PyMC com histórico intermediário de mídia, controles explícitos e intervalo posterior preditivo; Ridge aceita planos variáveis por período.
- Comparação exige linhagem/KPI/unidades compatíveis; interseção explícita alinha métricas e intervalos e nunca elege vencedor universal.
- Diagnósticos bayesianos explicáveis, viés preditivo, recuperação sintética/60 ajustes e advertência de bootstrap na fronteira nula.
- Painéis locais de qualidade, resíduos, componentes, curvas e exportações; abstenção explícita.
- CI preservado, limiar de cobertura medido, verificação de wheel em ambiente novo e workflows manuais de distribuição/motores Python.
- Conectores de anúncios permanecem contratos offline; sem OAuth, acesso a contas ou serviço público.

## 0.3.1 — segurança do transporte, workers e cadeia de suprimentos

- Workers herdam apenas ambiente permitido; falhas não repassam mensagem interna ao cliente. Saída nativa drenada/limitada a 1 MB.
- HTTP aceita expiração/bloqueio opcionais de token, rejeita Authorization duplicado e limita frequência/concorrência, preservando isolamento e papéis.
- Headers defensivos e dashboard com script autorizado por hash CSP; cálculo legítimo e bloqueio de script não autorizado verificados no Chrome.
- CI com dependências universais fixadas por hash, somente wheels, actions por SHA, credenciais não persistidas, mypy básico, Bandit e scanner de padrões/histórico.
- Testes de regressão, negativas HTTP reais, recuperação por cópia para raiz nova e recarga dos três motores opcionais. Auditoria completa em SECURITY_DEPLOY_AUDIT.md.
- Somente publicação de código no GitHub; nenhum deploy, recurso pago ou dado empresarial.

## 0.3.0 — auditoria científica e abstenção explícita

- Adicionada audit_model: decomposição reconciliada, backtesting com seleção nested, sensibilidade de especificação e insight rastreável.
- Corrigida influência do target reservado no pré-processamento Meridian e na busca Robyn; contagens de split Robyn seguem datas nativas.
- Persistidos priors/configuração efetiva, tipo de intervalo e diagnósticos MCMC completos sem arredondamento; ajustes curtos não certificados.
- Adicionados RMSE/MAPE, posto/condição padronizados, declaração do KPI e contexto de dados; advertências preservadas nos cenários.
- Otimização separa candidato numérico de recomendação, compara verba igual e expõe derivadas condicionais. ROI/mROI causal permanecem indisponíveis.
- Calibração bloqueia mistura de origens; bootstrap registra viés de penalização e cobertura não certificada.
- 105 testes, 11 casos sintéticos de stress e novas evidências nativas/UI; documentação científica e limites empresariais explícitos.

## 0.2.0 — primeira publicação do código

### Adicionado

- Servidor MCP oficial com 15 ferramentas, stdio e HTTP local autenticado com papéis e isolamento por usuário.
- MMM exploratório com adstock, saturação, Ridge com mídia não negativa, teste temporal e persistência imutável.
- Adaptadores reais opcionais Meridian, PyMC-Marketing e R Robyn; reconstrução nativa e cenários históricos.
- Otimização, bootstrap condicional, seleção temporal, calibração declarada, relatório e dashboard locais.
- Matriz CI para três sistemas e três versões Python; auditoria de dependências e evidências sintéticas públicas.

### Corrigido na revisão de publicação

- Tuning recusa dados inválidos também no holdout externo, sem selecionar hiperparâmetros usando esse holdout.
- Calibração recusa extremos numéricos em vez de retornar sucesso com NaN.
- Robyn rejeita splits diferentes do 60/20/20 nativo suportado.
- Entradas inválidas e falhas de resultados internos possuem classificação distinta; sucesso só é registrado após validar o envelope.
- Pacotes fonte excluem ambientes, logs, modelos e configurações pessoais; conteúdo real do wheel/sdist tem teste automatizado.
- Dependência de desenvolvimento pytest atualizada para 9.0.3 por advisory conhecido.

O software usa somente dados sintéticos na entrega. Integração executável não certifica convergência, adequação empresarial ou causalidade. Não há publicação no PyPI ou implantação de serviço.
# V4.2 — em desenvolvimento, sem nova publicação

- Aplicação local com dez módulos analíticos, temas e gráficos interativos; HTML offline preservado.
- Dashboard abre diretamente, sem login/token manual; endpoint MCP autenticado permanece separado.
- Recurso MCP de dataset com isolamento de tenant, testes web e de origem/loopback.
- Plugin local portável, ZIP reproduzível e templates de infraestrutura ainda não implantados.
