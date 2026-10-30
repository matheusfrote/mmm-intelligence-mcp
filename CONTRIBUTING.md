# Contribuição

Leia [arquitetura](docs/architecture.md), [método](docs/methodology.md) e
[segurança](docs/security.md). Use Python 3.11–3.13 e uma branch separada.

```sh
python -m venv .venv
# Ative a venv conforme seu sistema.
python -m pip install --require-hashes --only-binary=:all: -r requirements/base-ci.txt
python -m pip install --no-deps --no-build-isolation -e .
python -m pytest -q --cov=mmm_intelligence
python -m ruff check src tests examples server.py
python -m ruff format --check src tests examples server.py
python -m mypy src
python -m bandit -r src
python examples/check_secrets.py
```

Reproduza defeitos com teste que falha antes da correção. Não remova testes negativos.
Mudanças matemáticas devem informar estimando, dados, janela temporal, transformações,
incerteza e diferenças em relação ao framework nativo. Use somente dados sintéticos
em PRs; não publique modelos empresariais, logs privados nem credenciais.

Cada PR deve explicar problema, comportamento, testes executados, compatibilidade e
limites. Testes simulados de API não são homologação de conta. Smokes curtos não
certificam convergência. Contribuições submetidas para inclusão ficam sob Apache-2.0,
conforme seção 5 da licença, salvo acordo explícito diferente.

Versionamento SemVer: correções compatíveis incrementam patch; capacidades aditivas,
minor; alterações incompatíveis, major. Durante 0.x, anunciar migrações no changelog.
Contratos/artifacts possuem suas próprias versões. Não reescrever história compartilhada.

Veja [instalação](docs/installation.md), [release](docs/releasing.md) e
[roadmap](docs/roadmap.md). Não há promessa de SLA ou prazo de revisão.
