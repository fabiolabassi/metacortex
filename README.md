# Desafio 03: Metacortex

| Ticket | Pasta | Resumo |
|---|---|---|
| 01 · Skill do padrão de manifests | [`ticket-01-padrao-de-manifests/`](ticket-01-padrao-de-manifests/) | skill `padrao-de-manifests`: script (Trivy + o que ele não cobre) e instrução; conferência do manifesto barrado e escrita do fake-shop |
| 02 · Skill de triagem de cluster | [`ticket-02-triagem-no-cluster/`](ticket-02-triagem-no-cluster/) | skill `triagem-de-cluster` sobre o mcp-server-kubernetes (4 camadas de só leitura); 3 chamados; matriz de roteamento; com × sem skill |
| 03 · Inventário e drift de VM por SSH | [`ticket-03-inventario-de-vm/`](ticket-03-inventario-de-vm/) | CLI `roster-audit` (Python), PRD/TRD/ADRs, OpenSpec arquivado, evidência contra VMs Ubuntu reais (QEMU) |
| 04 · Dashboard do cluster | [`ticket-04-dashboard-do-cluster/`](ticket-04-dashboard-do-cluster/) | app `retrato` (Python, página local), 5 ADRs, OpenSpec arquivado, telas contra o kind e os 3 cenários de falha |

Cada pasta tem um `README.md` que aponta onde está cada item do "Entregue".

**Agente:** Claude Code 2.1.311. **Modelo:** Claude Opus 5.5 (`claude-opus-5-5`)
em todas as etapas e em todas as sessões de execução (`claude -p`).

As skills ficam instaladas como skills de projeto em `/.claude/skills/` (links
para as pastas dos tickets). O MCP de triagem está em `/.mcp.json`, e os
bloqueios de escrita em `/.claude/settings.json`.

Utilitário comum: [`ferramentas/resumo-sessao.py`](ferramentas/resumo-sessao.py)
resume uma sessão gravada (skill disparada, ferramentas, tokens, custo, tempo).
