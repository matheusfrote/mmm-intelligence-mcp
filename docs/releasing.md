# Preparação e publicação de versões

O workflow `release-check.yml` é manual e somente valida/builda. Não contém token de
publicação, permissão contents:write, criação de tag/release ou upload ao PyPI.
Após autorização específica, o mantenedor pode publicar artefatos previamente
revisados. O workflow não transforma uma aprovação genérica em publicação automática.

1. Revise diff, changelog, versão em pyproject/__init__, LICENSE/NOTICE e docs.
2. Rode suíte, tipos, Ruff, Bandit, scanner de segredos e pip-audit do lock.
3. Execute `python -m build --no-isolation --outdir dist/NOVA-VERSAO`.
4. Instale o wheel em venv nova e rode doctor + ciclo MCP real, de fora do checkout.
5. Inspecione wheel/sdist; não incluir var/evidence, modelos, logs ou configurações privadas.
6. Gere SHA-256 para ambos e registre commit, Python, build backend e lock.
7. Somente após autorização: commit/tag assinada se disponível, push normal, release
   com hashes/limites. PyPI requer conta/projeto/Trusted Publisher e aprovação própria.

Dependências base têm lock universal com hashes. Os builds atuais são reproduzíveis
quanto a entradas/versões verificadas, sem promessa de identidade binária de archives
entre horários/SOs. Fixe SOURCE_DATE_EPOCH no pipeline se desejar investigar esse nível.

## Proposta de proteção main (não aplicada)

Exigir pull request, uma revisão quando houver outro mantenedor, conversas resolvidas,
os nove checks de teste e security. Bloquear force push e exclusão; não permitir bypass
rotineiro. Para mantenedor solo, definir política de revisão viável antes de ativar.
Os nomes exatos devem ser os jobs observados do workflow no commit candidato.
Alterar regras pelo GitHub exige autorização específica e permissão de administração.

Dependabot foi preparado no código; não há auto-merge. Revisar também os hashes do lock
ao aceitar atualizações. Uma proposta de configuração não prova que regras remotas
estejam ativas nem que um novo CI tenha rodado.
