# Workspace local — V4.2

Abra a aplicação pelo servidor, **sem login e sem informar token**:

```powershell
.\var\envs\security31\Scripts\python.exe -m mmm_intelligence.cli dashboard --port 8772
```

Em outra instalação, use `mmm-intelligence-mcp dashboard` depois de instalar o pacote. O padrão é `http://127.0.0.1:8769/app`. Não abra `web/index.html` diretamente: o workspace precisa do servidor para consultar e persistir resultados. O **HTML exportado** continua independente e funciona offline.

Para iniciar com dados e um modelo sintéticos, execute `python examples/dashboard_preview.py`. O script respeita `MMM_PORT` e `MMM_DATA_DIR` e preserva artefatos existentes. Os arquivos do workspace ficam em `MMM_DATA_DIR/dashboard`; usuários autenticados do MCP continuam em `MMM_DATA_DIR/tenants/<usuário>`. Não há migração ou cópia automática entre esses diretórios.

## Acesso e limites

- `/app`: interface local, sem sessão, cookies, senha ou token.
- `/app/mcp`: ponte MCP exclusiva do dashboard. Exige conexão loopback, Origin idêntica ao Host e cabeçalho não simples; rejeita origens externas, preflight e cabeçalhos de proxy. Não configura CORS permissivo. **Nunca publique ou encaminhe `/app` e `/app/*` por proxy.**
- `/mcp`: mantém autenticação bearer, papéis e isolamento existentes. O comando `dashboard` não configura credenciais externas; portanto `/mcp` responde 401. `serve` com `MMM_USERS_JSON` continua habilitando os usuários configurados.
- Limites de tamanho, taxa, concorrência, cálculo, autorização de dados reais e persistência imutável permanecem aplicados. Qualquer pessoa/processo com acesso ao computador pode utilizar o workspace local, conforme a finalidade desse modo.

O servidor escuta somente `127.0.0.1`. A ponte local não é um mecanismo de autenticação para um serviço remoto.

## Fluxos disponíveis

Os dez módulos têm estados vazios, erros visíveis e indicadores de tempo decorrido, sem porcentagens inventadas. Data Explorer gera/importa CSV com metadados explícitos, filtra/pagina registros e exibe séries. Qualidade consulta alertas e estatísticas. Modelagem ajusta Ridge ou solicita os runtimes opcionais realmente configurados. Resultados preservam diagnósticos e semântica dos intervalos; comparação exige a mesma linhagem e uma janela explícita. Resposta de mídia apresenta curvas condicionais Ridge. Simulador executa cenário, otimização com restrições e projeções quando suportadas. Insights preserva limites científicos. Relatórios exporta JSON/CSV/Markdown e HTML offline Ridge.

Gráficos oferecem seleção de séries, janela temporal, leitura por ponteiro/setas e CSV. O tema segue o sistema ou pode ser escolhido. Não há dependência JavaScript em produção, CDN ou telemetria. Node e as dependências em `package.json` são somente para desenvolvimento/testes.

Não há decomposição nativa unificada, curvas analíticas Meridian/Robyn/PyMC, treinamento offline nem fila durável de trabalhos. Operações indisponíveis são identificadas na interface. Os parâmetros avançados usam JSON validado pelo contrato MCP.

## Verificação reproduzível

```powershell
python -m pytest tests/test_web_app.py tests/test_appsec.py tests/test_cli.py -q
npm ci --ignore-scripts
$env:MMM_TEST_PYTHON = (Resolve-Path '.venv/Scripts/python.exe').Path
npm run test:web
```

O teste web requer Chrome instalado e abre um servidor temporário com dados sintéticos. Verifica ausência de credenciais, ciclo real de ferramentas, igualdade dos números mostrados com a resposta MCP, download, teclado, 320/390/768/1024/1440 px e axe-core nos temas claro/escuro. O scanner é carregado por interceptação **apenas no teste**, mantendo a CSP real. Esse teste automático não equivale a certificação WCAG ou validação com leitor de tela.
