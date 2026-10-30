# Ticket 03: inventário e drift de VM por SSH (`roster-audit`)

CLI que audita **uma** VM por SSH, a partir da estação do operador e sem
agente no host, e compara o estado real com o `baseline.yaml` do parque.
Saída em JSON (Roster) e Markdown (plantão), com código de saída para pipeline.

```bash
pip install .            # ou: PYTHONPATH=src python3 -m roster_audit ...
roster-audit --endereco 10.42.7.14 --usuario auditor --chave ~/.ssh/auditoria [--sudo] [--formato json]
```

| Código | Significado |
|---|---|
| 0 | todas as regras conformes |
| 1 | pelo menos um desvio |
| 2 | sem desvio, mas com regra `nao_verificado` |
| 3 | erro de uso (argumento, baseline, chave) |
| 4 | host inalcançável ou autenticação recusada |

## Onde está cada item pedido

| Entregue | Onde |
|---|---|
| **Documentos de spec** | [`docs/00-brainstorm.md`](docs/00-brainstorm.md), [`docs/01-PRD.md`](docs/01-PRD.md), [`docs/02-TRD.md`](docs/02-TRD.md) |
| ↳ ADRs (as três decisões pedidas) | [ADR-0001: comunicação com o host](docs/adr/0001-ssh-do-sistema-e-coleta-numa-sessao.md) · [ADR-0002: dado não coletado](docs/adr/0002-dado-nao-coletado-vira-nao-verificado.md) · [ADR-0003: linguagem](docs/adr/0003-python-com-biblioteca-padrao.md) |
| **Artefatos do OpenSpec** (proposta, tarefas, specs, arquivado) | change arquivada em [`openspec/changes/archive/2026-10-26-auditoria-de-vm-por-ssh/`](openspec/changes/archive/2026-10-26-auditoria-de-vm-por-ssh/) (`proposal.md`, `design.md`, `tasks.md`, `specs/`); specs consolidadas após o arquivamento em [`openspec/specs/`](openspec/specs/) |
| **O código** | [`src/roster_audit/`](src/roster_audit/) (o script remoto é [`coleta.sh`](src/roster_audit/coleta.sh)); testes em [`tests/`](tests/), com fixtures reais das VMs |
| **Evidência: saída nos dois formatos** | [`evidencias/01-host-conforme/`](evidencias/01-host-conforme/) e [`evidencias/02-host-com-desvios/`](evidencias/02-host-com-desvios/): `*-markdown.stdout` e `*-json*.stdout` |
| **Evidência: código de retorno** | cada caso tem `.cmd` com o comando e o código de saída |
| **Evidência: host inalcançável** | [`evidencias/03-host-inalcancavel/`](evidencias/03-host-inalcancavel/): endereço sem resposta, nome inexistente, SSH fora do ar, chave recusada, chave com permissão aberta, chave inexistente, host desconhecido, chave do host mudou; mais [`chave-nao-exposta.txt`](evidencias/03-host-inalcancavel/chave-nao-exposta.txt) |
| **Evidência: segunda execução igual** | [`evidencias/01-host-conforme/determinismo.txt`](evidencias/01-host-conforme/determinismo.txt), [`evidencias/02-host-com-desvios/determinismo.txt`](evidencias/02-host-com-desvios/determinismo.txt) |
| **Curadoria** (onde a spec mudou; o que o agente entendeu diferente) | [`docs/03-curadoria.md`](docs/03-curadoria.md) |

## Critérios de pronto × evidência

| Critério | Resultado | Evidência |
|---|---|---|
| CA-1 host conforme sai sem desvio | 11/11 conforme, código **0** | `01-host-conforme/com-sudo-markdown.stdout` |
| CA-2 desvios com a severidade do baseline | 8 desvios (4 crítico, 3 alto, 1 médio), código **1** | `02-host-com-desvios/com-sudo-markdown.stdout` |
| CA-3 `nao_verificado` separado de conforme | sem `--sudo`: `ssh.login_de_root` e `chaves_ssh.emitidas_por` em seção própria, código **2** | `01-host-conforme/sem-sudo-markdown.stdout` |
| CA-4 inalcançável explicado, sem stack trace, não confundido com conforme | 8 cenários, mensagem de uma linha no stderr, stdout vazio, código **4** (ou 3 para chave inexistente) | `03-host-inalcancavel/*.stderr` |
| CA-5 segunda execução igual | JSON idêntico, exceto `coletado_em` (5 s de diferença) | `*/determinismo.txt` |
| RNF-01 só leitura | durante a auditoria, só mudaram `auth.log`, `syslog` e o journal (login/sudo); nada em `/tmp` nem em `/home` | `01-host-conforme/somente-leitura.txt` |
| RNF-03 a chave não aparece | nenhuma saída contém o caminho nem o conteúdo da chave | `03-host-inalcancavel/chave-nao-exposta.txt`, teste `test_classificacao` |

### A VM com desvios, em Markdown

```
# Inventário de construct-node-02 (127.0.0.1)
Coletado em 2026-10-27 00:02 UTC · baseline v1

## Desvios

| Severidade | Regra | Esperado | Encontrado |
|---|---|---|---|
| crítico | swap.habilitado | false | true (512M) |
| crítico | portas_em_escuta.publicas_permitidas | só 22 pública | 23 em * (systemd), 111 em 0.0.0.0 (rpcbind), 111 em :: (rpcbind) |
| crítico | portas_em_escuta.somente_rede_interna | 9100 na rede interna | 9100 em * |
| crítico | chaves_ssh.emitidas_por | todas emitidas por metacortex-platform | auditor: dozer@notebook |
| alto | servicos.ativos | chrony ativo | ausente |
| alto | servicos.proibidos | telnet.socket, rpcbind.socket inativos | rpcbind.socket, telnet.socket ativos |
| alto | ssh.login_de_root | false | true (yes) |
| médio | kernel.versao_minima | 6.5 | 5.15.0-198-generic |

## Conforme
so.distribuicao · so.versao_minima · ntp.sincronizado
```

## Laboratório (hosts reais por SSH)

Duas VMs Ubuntu em QEMU/KVM com rede de usuário, sem root e sem libvirt.
A configuração vem de cloud-init:

| VM | Imagem | SSH | Para quê |
|---|---|---|---|
| `construct-node-01` | Ubuntu 24.04 (kernel 6.8) | `127.0.0.1:2221` | dentro do baseline: chrony, containerd, node_exporter só em `10.0.2.15`, sem swap, `PermitRootLogin no` |
| `construct-node-02` | Ubuntu 22.04 (kernel 5.15) | `127.0.0.1:2222` | um desvio planejado por regra ([`lab/cloud-init/desvios.yaml`](lab/cloud-init/desvios.yaml)) |

```bash
bash lab/vm.sh criar conforme            # sobe a VM (cloud-init ~2 min)
bash lab/evidencias.sh conforme          # regrava evidencias/01-host-conforme
bash lab/evidencias.sh inalcancavel      # não precisa de VM
PYTHONPATH=src python3 -m unittest discover -s tests -v
bash lab/vm.sh parar conforme
```

O endereço nas evidências é `127.0.0.1`, porque a porta é encaminhada pelo
QEMU. O hostname reportado pelo host (`construct-node-0N`) vem do próprio host.

**Agente e modelo:** Claude Code 2.1.311 com Claude Opus 5.5 (`claude-opus-5-5`).
