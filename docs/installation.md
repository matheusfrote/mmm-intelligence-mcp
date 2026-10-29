# Instalação e integração MCP

Python 3.11, 3.12 ou 3.13. O pacote base não instala TensorFlow, PyMC ou R.
O nome ainda não foi publicado no PyPI: `pip install mmm-intelligence-mcp` não é
uma instrução disponível enquanto não houver publicação autorizada.

## Checkout ou wheel

```sh
git clone --branch feat/v4-intelligence https://github.com/matheusfrote/mmm-intelligence-mcp.git
cd mmm-intelligence-mcp
python -m venv .venv
```

Windows: `.venv\Scripts\Activate.ps1`. Linux/macOS: `source .venv/bin/activate`.
Instalação simples do checkout: `python -m pip install .`. Para reproduzir as versões
do CI e ferramentas de desenvolvimento:

```sh
python -m pip install --require-hashes --only-binary=:all: -r requirements/base-ci.txt
python -m pip install --no-deps --no-build-isolation -e .
mmm-intelligence-mcp doctor
mmm-intelligence-mcp config --data-dir /CAMINHO/ABSOLUTO/mmm-data
```

No Windows, use por exemplo `--data-dir C:\mmm-data`. `config` imprime JSON; copie para
o cliente MCP. Não grava configuração global, não inclui tokens e fixa stdio/dados
sintéticos. `doctor` verifica metadados base e presença de executáveis opcionais;
não afirma que bibliotecas nativas foram importadas. `mmm-intelligence-mcp` sem
argumentos e `mmm-intelligence-mcp serve` mantêm o servidor; o silêncio inicial é
esperado, pois stdout é reservado para o protocolo.

Wheel: `python -m pip install /caminho/mmm_intelligence_mcp-VERSAO-py3-none-any.whl`.
Use o hash SHA-256 publicado junto ao artefato. GitHub por commit:
`python -m pip install "git+https://github.com/matheusfrote/mmm-intelligence-mcp.git@COMMIT"`.
Substitua COMMIT por um hash publicado e revisado da branch. A V4.2 está em
`feat/v4-intelligence`; clonar a main não seleciona esta entrega.

## pipx e uvx

O console script é compatível com ambientes isolados. A partir de checkout, com as
ferramentas previamente instaladas: `pipx install .` ou `uvx --from . mmm-intelligence-mcp doctor`.
Esses gerenciadores resolvem dependências próprias; o lock de desenvolvimento não é
aplicado automaticamente. A verificação de wheel limpo é a evidência de empacotamento;
não equivale a homologação de todas as versões de pipx/uvx ou clientes desktop.
Em 28/10/2026 foram verificados o wheel 0.4.0 com uvx 0.12.12 e pipx 1.18.7,
em Windows/Python 3.12.14, usando diretórios isolados dentro do projeto e sem
alterar o PATH global. Os resultados e o alcance dos testes estão no
[registro de continuação](v42-followup.md).

## Motores opcionais e problemas comuns

Siga [operações](operations.md) e use runtimes separados para Meridian, PyMC e Robyn.
Nunca instale os três ambientes pesados na venv base. Configure caminhos absolutos
MMM_*_PYTHON e MMM_RSCRIPT. BACKEND_UNAVAILABLE significa executável ausente;
BACKEND_FAILED exige revisar o log privado local. BUSY requer aguardar o cálculo;
ARTIFACT_TOO_LARGE requer revisar o tamanho e a política do host. O limite HTTP de
4 MiB pode ser menor que o limite do artefato. Não exponha a porta loopback na Internet.

No Windows, erro de política de execução não exige mudar a política global: invoque
diretamente `.venv\Scripts\python.exe`. Para detalhes de clientes e contratos, veja
[ferramentas](tools.md). Os runtimes opcionais não têm suporte garantido em todas as
nove combinações de OS/Python da base.
