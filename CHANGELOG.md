# Changelog

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
