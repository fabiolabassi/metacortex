# Mapa de conformidade

Cada regra do padrão, onde ela é atendida nos manifests e quem verifica.

- **auto**: `scripts/check_padrao.py` reprova (ERRO) ou avisa (AVISO) sozinho,
  com teste negativo em `exemplos/reprovados/`
- **trivy**: a varredura de configuração também pega (ver o achado 6 da
  [revisão](revisao-do-padrao.md#6-a-varredura-do-trivy-não-cobre-o-que-o-bloco-3-dá-a-entender)
  para saber em que severidade)
- **cluster**: o apiserver ou o Pod Security `restricted` recusa (job `admissao` da CI)
- **revisão**: continua sendo trabalho do revisor no PR

## Bloco 1 — Identidade e nomenclatura

| Regra | Onde | Verificação | Anti-padrão |
| --- | --- | --- | --- |
| 1.1 kebab-case | todo `metadata.name` | auto | 01 |
| 1.2 `<cliente>-<ambiente>` | `nyx-prod`, `nyx-dev`; todo objeto declara `namespace` | auto | 01 |
| 1.3 quatro rótulos | objeto, `jobTemplate` e `template` do pod; `instance` = namespace, `part-of` = cliente | auto | 01, 07 |
| 1.4 seletor casa com o pod | `matchLabels` ⊂ rótulos do template; `Service.selector`, `targetPort` nomeado e seletor de PDB cruzados com os pods do namespace | auto + cluster (só Deployment) | 01, 02 |
| 1.5 owner/runbook (rec.) | `metacortex.io/owner` em todo objeto, `runbook` em todo workload | auto (aviso) | 01 |
| 1.6 container = componente (rec.) | `api`, `worker`, `reconcile` | auto (aviso) | 01 |

O seletor usa só `name` + `instance`. `matchLabels` é imutável depois de
criado, e `managed-by` muda quando o workload sair de `platform` para `argocd`.
O rótulo curto `app:` não é usado: nenhum seletor antigo depende dele aqui.

## Bloco 2 — Resiliência

| Regra | Onde | Verificação | Anti-padrão |
| --- | --- | --- | --- |
| 2.1 requests e limits | todo container | auto + trivy (LOW) | 01 |
| 2.2 readiness e liveness | `api`: `/readyz` × `/healthz`; `worker`/`reconcile`: arquivos `ready` × `heartbeat` | auto: presença, probes idênticas, porta nomeada que existe | 01 |
| 2.3 réplicas ≥ 2 em prod | `replicas: 2` em `nyx-prod`, `1` em `nyx-dev` | auto (só `*-prod`) | 04, 06 |
| 2.4 RollingUpdate 0/1 | todos os Deployments (em dev também, para ensaiar) | auto (só `*-prod`) | 04 |
| 2.5 PDB em prod (rec.) | `32-pdb-api.yaml`, `41-pdb-worker.yaml` + `topologySpreadConstraints` | auto (aviso), inclusive `minAvailable` ≥ réplicas | 04 |
| 2.6 grace period (rec.) | `api` 30s + `preStop` 5s; `worker` 120s; `reconcile` 60s | revisão | — |

**2.2 em detalhe.** O wiki avisa que readiness e liveness no mesmo endpoint
que checa banco derrubam a aplicação quando o banco fica lento. Aqui:

- `readyz` checa dependências. Falhou, o pod sai do Service e não reinicia.
- `healthz` só diz que o processo responde.
- `startupProbe` (4.8) dá 60s de carência na partida sem afrouxar a liveness.
- No `worker`, `ready` some quando a conexão com a fila cai, e `heartbeat`
  para de ser tocado quando o loop trava. É a mesma separação entre "posso
  receber trabalho" e "estou vivo".

## Bloco 3 — Segurança

| Regra | Onde | Verificação | Anti-padrão |
| --- | --- | --- | --- |
| 3.1 sem `:latest` | `:2.9.1`; imagem sem tag também reprova | auto + trivy | 01, 06 |
| 3.2 securityContext | Pod: `runAsNonRoot`, `runAsUser/Group`, `fsGroup`, `seccompProfile`. Container: `allowPrivilegeEscalation`, `readOnlyRootFilesystem`, `privileged: false`, `drop: ALL` | auto (inclui campo no nível errado) + trivy + cluster | 01, 05 |
| 3.3 sem segredo em texto | `secretKeyRef` para `nyx-db` e `nyx-queue`; nenhum Secret no Git | auto: `env.value`, ConfigMap, Secret versionado, comentário | 01, 03 |
| 3.4 automount false | no Pod **e** na ServiceAccount | auto | 01 |
| 3.5 SA dedicada (rec.) | `nyx-api`, `nyx-worker`, `nyx-reconcile`, sem RBAC | auto (aviso; também SA compartilhada) | 01 |
| 3.6 host*/privileged | ausentes; Pod Security `restricted` recusa | auto + trivy + cluster | 01 |
| 3.7 registry interno | `registry.metacortex.io/nyx/...` | auto + trivy (com `.trivy/data`) | 01 |

`readOnlyRootFilesystem` exige caminho gravável declarado. `api` monta
`emptyDir` em `/tmp` e `/var/cache/nyx-api`. `worker` e `reconcile` montam
`/tmp` e `/var/run/nyx`, onde ficam os arquivos lidos pelas probes (em
memória, com `sizeLimit`).

## O que continua sendo revisão humana

Nenhuma ferramenta decide estes pontos, e é neles que o tempo do revisor rende:

- se `limits.memory` está mesmo entre 1,5x e 2x o consumo em regime (2.1);
- se `/readyz` e `/healthz` existem na aplicação e fazem o que o nome diz (2.2);
- se o grace period cobre o pior caso e se a aplicação trata SIGTERM (2.6);
- se a tag é a que o pipeline promoveu (3.1);
- se a ServiceAccount realmente não fala com o apiserver (3.4/3.5);
- se uma exceção anotada tem aprovação de verdade de Segurança & Compliance.
