# Ticket 04: dashboard de leitura do cluster (`retrato`)

Aplicação local (Python + página única em `127.0.0.1:8765`) que mostra o
retrato de um namespace do **contexto corrente** do kubeconfig. Só leitura.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python -m retrato            # abre http://127.0.0.1:8765
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

## Onde está cada item pedido

| Entregue | Onde |
|---|---|
| Documentos de spec | [`docs/00-brainstorm.md`](docs/00-brainstorm.md), [`docs/01-PRD.md`](docs/01-PRD.md), [`docs/02-TRD.md`](docs/02-TRD.md) |
| ADRs (5 decisões em aberto) | [stack](docs/adr/0001-stack-python-stdlib-http-e-pagina-unica.md) · [acesso à API](docs/adr/0002-cliente-oficial-python.md) · [atualização](docs/adr/0003-atualizacao-por-intervalo-fixo.md) · [EndpointSlice](docs/adr/0004-endpointslice.md) · [primeira fatia](docs/adr/0005-recorte-da-primeira-fatia.md) |
| Artefatos do OpenSpec | [`openspec/changes/archive/2026-10-26-retrato-do-namespace/`](openspec/changes/archive/2026-10-26-retrato-do-namespace/); specs consolidadas em [`openspec/specs/`](openspec/specs/) |
| Código | [`src/retrato/`](src/retrato/) (só [`leitura.py`](src/retrato/leitura.py) fala com a API); testes em [`tests/`](tests/), saída em [`evidencias/testes.txt`](evidencias/testes.txt) |
| Execução contra o cluster | [`evidencias/01-cluster-real/`](evidencias/01-cluster-real/): telas e JSON dos chamados (`nyx-prod`, `orion-stg`, `nyx-stg`) e dos workloads (`orion-prod`, `nyx-dev`) |
| Os três cenários de falha | [`02-cluster-inacessivel`](evidencias/02-cluster-inacessivel/), [`03-credencial-expirada`](evidencias/03-credencial-expirada/) (token que expirou de verdade), [`04-permissao-negada-events-endpointslices`](evidencias/04-permissao-negada-events-endpointslices/), [`05-permissao-negada-namespaces`](evidencias/05-permissao-negada-namespaces/); cada um com `console.log` sem traceback |
| Registro das skills | [`observacao-skills/README.md`](observacao-skills/README.md) |
| Curadoria (spec corrigida, agente divergente, justificativa estendida) | [`docs/03-curadoria.md`](docs/03-curadoria.md) |

## Pré-requisitos atendidos

- Dois projetos em namespaces separados, com manifests da skill do Ticket 01:
  fake-shop em `orion-prod` (Ticket 01) e kube-news em `nyx-dev`
  ([`workloads/nyx-dev/`](workloads/nyx-dev/), gerado pela skill nesta fase).
  Os dois sobem com Pod Security `restricted`. Subida: [`lab/subir-workloads.sh`](lab/subir-workloads.sh).
- As skills dos Tickets 01 e 02 instaladas em `/.claude/skills/`.

## Só leitura, visível no projeto

1. **Código:** [`tests/test_somente_leitura.py`](tests/test_somente_leitura.py) analisa a AST e falha com qualquer verbo que não seja `list_`/`read_`, ou com outro módulo importando `kubernetes`. Ele também prova que pega uma escrita plantada.
2. **HTTP:** só `do_GET`; POST/PUT/PATCH/DELETE → 405; escuta só em `127.0.0.1` (testado).
3. **RBAC:** [`deploy/rbac-retrato-leitura.yaml`](deploy/rbac-retrato-leitura.yaml) + [`deploy/gera-kubeconfig.sh`](deploy/gera-kubeconfig.sh); prova em [`deploy/prova-auth-can-i.txt`](deploy/prova-auth-can-i.txt); execução com ela em [`evidencias/06-papel-de-leitura/`](evidencias/06-papel-de-leitura/).

**Agente e modelo:** Claude Code 2.1.311 com Claude Opus 5.5 (`claude-opus-5-5`).
