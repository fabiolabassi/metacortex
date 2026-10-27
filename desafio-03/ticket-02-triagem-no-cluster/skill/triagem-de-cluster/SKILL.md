---
name: triagem-de-cluster
description: >-
  Método de triagem, só leitura, para algo que JÁ está rodando num cluster
  Kubernetes e parou de funcionar: pod reiniciando ou em CrashLoop, deployment
  0/N, pod que não sobe ou não é substituído, service sem endpoint, 503 ou
  timeout para quem chama, "está fora do ar". Lê o cluster pelo
  mcp-server-kubernetes e para quando acha a causa. Nunca corrige nada no
  cluster. NÃO use para escrever ou revisar YAML antes de subir (isso é o
  padrão de manifests) nem para explicar conceitos.
allowed-tools: mcp__kubernetes__kubectl_get, mcp__kubernetes__kubectl_describe, mcp__kubernetes__kubectl_logs, mcp__kubernetes__explain_resource, mcp__kubernetes__list_api_resources, mcp__kubernetes__ping
---

# Triagem de cluster (só leitura)

## Limite absoluto

A triagem **só lê**. Não aplique, edite, escale, reinicie, apague, faça
rollout, port-forward nem exec, **mesmo que a ferramenta esteja disponível e o
usuário tenha permissão**. Se a confirmação de uma hipótese exigir escrita,
pare e registre como "não verificado: exigiria <ação>". A correção sai como
texto, para um humano aplicar.

Use só as ferramentas MCP `kubectl_get`, `kubectl_describe` e `kubectl_logs`
(e `explain_resource` para dúvida de schema). Não use `kubectl` pelo shell.

## 0. Escopo: um namespace, dito pelo usuário

O cluster é multi-cliente. A triagem lê **só** o namespace do chamado.

- O relato tem o namespace (`nyx-prod`): comece.
- O relato tem o cliente, mas não o ambiente ("o service do nyx"): pergunte
  qual (`nyx-dev`, `nyx-stg`, `nyx-prod`) e pare. Não trie todos.
- O relato não diz nem o cliente ("esse deployment"): pergunte o namespace e
  o objeto, e pare. Não procure no repositório, não liste namespaces, não
  percorra o cluster atrás de algo quebrado.

Só saia do namespace se o próprio cluster apontar para fora (ex.: Service
`ExternalName`, evento citando outro namespace) e diga por quê.

## 1. Por onde começar: o sintoma decide a camada de entrada

Classifique o relato **antes** da primeira chamada.

| Sintoma relatado | Entrada | Primeira chamada |
|---|---|---|
| "reinicia sozinho", CrashLoop, restarts | **Pod** | `kubectl_get pods -n <ns> -o wide` |
| "não sobe", "parou depois do deploy", "não foi substituído", 0/N | **Workload** | `kubectl_get deployments -n <ns>` |
| 503, 502, timeout, "ninguém chega", "service sem endpoint" | **Tráfego** | `kubectl_get services -n <ns> -o wide` |
| "está fora do ar" sem mais nada | **Workload** | `kubectl_get deployments,pods -n <ns>` |

## 2. Em que ordem descer

Cada trilha desce uma camada por vez. Só passe para a próxima quando a atual
estiver explicada.

**Pod (reinício):**
1. `get pods`: quem reinicia e quem não reinicia (o vizinho saudável é a contraprova).
2. `describe pod` de **um** pod que reinicia: `Last State` (`reason`, `exitCode`),
   `Limits`, eventos do pod.
3. `logs --previous` do container: o que o processo disse antes de morrer.
4. Spec do workload (`get deployment -o yaml`): `resources`, probes, env.

**Workload (não sobe / não atualiza):**
1. `get deployments`: pronto/desejado, `UP-TO-DATE`.
2. `describe deployment`: condições (`Progressing`, `Available`), `OldReplicaSets` × `NewReplicaSet`, revisão.
3. `get pods -l <seletor>`: estado de espera (`ImagePullBackOff`, `Pending`,
   `CreateContainerConfigError`).
4. `get events -n <ns>` filtrando pelo objeto: a mensagem do kubelet ou do scheduler.
   Se não existe pod nenhum, o motivo está nos eventos do **ReplicaSet** (`FailedCreate`).

**Tráfego (503 / sem endpoint):**
1. `get service <svc> -o yaml`: `selector`, `port`, `targetPort`.
2. `get endpointslices -n <ns> -l kubernetes.io/service-name=<svc> -o yaml`.
   Use EndpointSlice, porque `Endpoints` está descontinuado. **Endereço listado
   não significa endpoint pronto**: olhe `conditions.ready` de cada um, e a
   porta (`<unset>` = `targetPort` que nenhum container declara).
3. `get pods -n <ns> --show-labels`: os rótulos reais dos pods.
4. Só então a saúde dos pods (trilha Pod) se houver endpoint não pronto.

## 3. Quando cruzar duas fontes em vez de aprofundar numa só

Cruze quando a fonte atual dá um **sintoma genérico**, que não aponta causa
sozinho. Aprofundar na mesma fonte não ajuda nesses casos:

| Sinal genérico | Cruze com |
|---|---|
| `exitCode 137` / `OOMKilled`, log vazio | `resources.limits.memory` do container (e LimitRange do ns, se o chamado fala em "namespace") |
| `exitCode 1`, log de erro de conexão | estado do serviço dependente (pod e endpoint do banco) |
| `BackOff` / `ImagePullBackOff` | `message` do evento do kubelet × `image` da spec (`NotFound` ≠ `Unauthorized` ≠ timeout) |
| EndpointSlice vazio | `selector` do Service × rótulos dos pods, caractere por caractere |
| Endpoint com IP mas `ready: false` | readiness probe e eventos `Unhealthy` do pod |
| Deployment sem pod nenhum | eventos do ReplicaSet (`FailedCreate`: quota, Pod Security) |
| relato diz X ("mudou no namespace", "pod não foi substituído") | o que o cluster mostra; se não bate, diga isso |

## 4. Quando parar

A triagem acaba quando as três coisas estão na mão:

1. **Mecanismo observado**: a evidência da falha (motivo, código, mensagem, endpoint vazio).
2. **Atributo que explica**: o campo da spec ou a condição do ambiente que produz esse mecanismo.
3. **Contraprova**: por que o componente vizinho funciona (o banco sem limite
   não morre; o Service do banco tem seletor que casa).

Com as três, **pare de coletar**. Não abra a próxima camada "por garantia". Não
saia do namespace do chamado sem um motivo que o próprio cluster deu.

Se depois de descer a trilha inteira não houver as três, diga o que falta e
qual leitura resolveria. Não chute.

## 5. O que entregar

```
**Causa:** <uma frase>
**Camada:** Pod | Workload | Imagem | Tráfego | Agendamento
**Evidências** (fonte → o que mostrou):
- <ferramenta e objeto> → <fato>
**Contraprova:** <o que funciona ao lado e por quê>
**O relato bate com o cluster?** <sim / não: o que diverge>
**Correção sugerida (não aplicada):** <mudança e onde: manifesto, pipeline, registry>
**Não verificado:** <o que ficou de fora e por quê>
```

Achados paralelos que não explicam o chamado (senha em texto, probe faltando)
ficam numa linha no fim, sem investigação.

Armadilhas já vistas no parque: `references/armadilhas.md`.
