# Saída real da triagem dos três chamados (com a skill)

Sessões limpas: `claude -p` com o texto do chamado
(`execucoes/prompts.sh`), MCP só de leitura e a skill instalada. A skill
**não** foi citada no pedido e disparou sozinha nas seis execuções.

A saída completa de cada execução está em `execucoes/com-skill/chamado-N.md`
(rep. 1) e `chamado-N.r2.md` (rep. 2).

## Resumo

| Chamado | Namespace | Sintoma relatado | Camada | Causa identificada |
|---|---|---|---|---|
| 1 | `nyx-prod` | "a API reinicia sozinha" | Pod | `limits.memory: 24Mi` no Deployment `nyx-api`: o Node é morto por OOM (`exitCode 137`) ~1 s após iniciar |
| 2 | `orion-stg` | "o pod nunca foi substituído" | Imagem | a tag `fabricioveronez/fake-shop:v1.14.2` não existe (`NotFound` no pull), e os 3 pods ficam em `ImagePullBackOff` |
| 3 | `nyx-stg` | 503 de fora, "app saudável" | Tráfego | o seletor do Service `app: nyx-api` não casa com o rótulo dos pods `app: nyxapi`; EndpointSlice vazio |

Em todos, há componente funcionando ao lado: o Postgres de cada namespace. A
skill usou esse componente como contraprova.

## Chamado 1: nyx-prod (rep. 1, na íntegra)

> **Causa:** o container `api` do `nyx-api` tem `limits.memory: 24Mi`. O Node do kube-news passa desse limite ao subir e o kernel mata o processo (OOMKilled) cerca de 1 s depois de iniciar, em loop.
>
> **Camada:** Pod
>
> **Evidências** (fonte → o que mostrou):
> - `get pods -n nyx-prod` → as 2 réplicas do `nyx-api` estão `OOMKilled`, 0/1, com 6 restarts cada. O `nyx-postgres` está 1/1, sem nenhum restart.
> - `describe pod nyx-api-656789474b-9f7q6` → `Reason: OOMKilled` e `Exit Code: 137`, tanto no estado atual quanto no anterior. Entre `Started` e `Finished` passa 1 s (20:42:28 → 20:42:29). `Limits: memory 24Mi`, `Requests: memory 16Mi`. Eventos com `BackOff` (x8).
> - `get limitranges,resourcequotas -n nyx-prod` → lista vazia. Não existe nenhum limite aplicado ao namespace.
> - `get deployments -o yaml` → o `24Mi` está escrito direto no spec do Deployment `nyx-api` (e no `last-applied-configuration`).
>
> **Contraprova:** o `nyx-postgres`, no mesmo namespace e no mesmo nó, está com `resources: {}`, ou seja, sem limite. Ele está `Running` sem restarts, então o nó e o banco estão bem. Só morre o container que tem o limite de 24Mi.
>
> **O relato bate com o cluster?** Em parte. O sintoma bate. Mas o cluster não mostra limite "no namespace inteiro": não há LimitRange nem ResourceQuota, e o banco nem tem limite. O corte foi feito no manifesto do `nyx-api`. […]
>
> **Correção sugerida (não aplicada):** no manifesto do `nyx-api`, subir a memória para um valor realista para Node, por exemplo `requests.memory: 128Mi` e `limits.memory: 256Mi`, e reaplicar. Se o objetivo do corte de custos era ter um teto por namespace, isso deve virar uma LimitRange/ResourceQuota com valores medidos, não um número colado no Deployment.
>
> **Não verificado:** não rodei `logs --previous`. Quando o processo morre por OOM em cerca de 1 s, normalmente não sobra log, e o par `137`/`OOMKilled` já fecha a causa. […]

## Chamado 2: orion-stg (rep. 1, trechos)

> **Causa:** a imagem `fabricioveronez/fake-shop:v1.14.2` não existe no registry. O kubelet recebe `NotFound` ao baixá-la, e os 3 pods do `orion-web` ficam presos em `ImagePullBackOff`.
>
> **Camada:** Imagem
>
> **Evidências:** […] `get events -n orion-stg` → o kubelet repete a mesma mensagem nos 3 pods: `failed to resolve reference "docker.io/fabricioveronez/fake-shop:v1.14.2": ... not found`. É `NotFound`, não `unauthorized` nem timeout. […] `describe deployment orion-web` → revisão **1**, `OldReplicaSets: <none>`.
>
> **Contraprova:** o `orion-postgres`, no mesmo namespace e no mesmo nó, baixou `postgres:16-alpine` sem erro e está 1/1 Running. Então o nó, a rede e o acesso ao Docker Hub funcionam. O que falha é só a referência `v1.14.2`.
>
> **O relato bate com o cluster?** Só em parte. […] Não houve substituição de pod que travou. O Deployment está na revisão 1 e não tem ReplicaSet antigo: ele foi recriado do zero, então nenhuma versão anterior estava servindo, e por isso a loja caiu por completo.

Conferido fora do cluster, só para esta documentação: o Docker Hub tem 18
tags em `fabricioveronez/fake-shop` (`1`, `latest`, `v1`, `v2`, `v6`–`v9`,
`v11`–`v17`, `v19`, `v20`, `v26`). **Não há `v1.14.2`**: a API de tags devolve
404 para ela. É provável que o release tenha anunciado um esquema de versão
(`v1.14.2`) que o repositório não usa (`v14`).

## Chamado 3: nyx-stg (rep. 1, trechos)

> **Causa:** o Service `nyx-api` seleciona `app=nyx-api`, mas os pods do kube-news têm o rótulo `app=nyxapi` (sem o hífen). O seletor não casa com nenhum pod, o EndpointSlice fica vazio e o tráfego que chega ao Service não tem para onde ir.
>
> **Camada:** Tráfego
>
> **Evidências:** `get endpointslices -n nyx-stg` → o slice `nyx-api-47trx` tem `endpoints: null` e `ports: null`. […] `get pods -l app=nyx-api` → não retorna nenhum pod. `get pods -l app=nyxapi` → retorna os 2 pods, ambos 1/1 Running.
>
> **Contraprova:** o `nyx-postgres` funciona porque o seletor do Service (`app=nyx-postgres`) é idêntico ao rótulo do pod. O slice dele tem `ready: true` na porta 5432.
>
> **Não verificado:** quem devolve o 503. Não olhei Ingress nem Gateway. Um endpoint vazio produz esse sintoma em qualquer proxy que esteja na frente do Service.

## Estado do cluster no momento da triagem

```
== nyx-prod
pod/nyx-api-656789474b-9f7q6       0/1     CrashLoopBackOff   4 (78s ago)   3m33s
pod/nyx-api-656789474b-dmr9f       0/1     OOMKilled          5 (89s ago)   3m33s
pod/nyx-postgres-f6fdc6dbf-47xmd   1/1     Running            0             3m33s
endpointslice.discovery.k8s.io/nyx-api-glvct   IPv4   8080   10.244.0.16,10.244.0.17
== orion-stg
pod/orion-web-67cd86ffd5-4969z        0/1     ImagePullBackOff   0          3m33s
deployment.apps/orion-web        0/3     3            0           3m33s
== nyx-stg
pod/nyx-api-7f4487c6ff-trfpw       1/1     Running   0               3m33s
endpointslice.discovery.k8s.io/nyx-api-47trx        IPv4   <unset>   <unset>
```

No `nyx-prod`, o EndpointSlice lista **dois IPs** com o Deployment em 0/2. Os
endpoints estão lá com `ready: false`. É a armadilha "endereço listado não é
endpoint pronto", que a skill registra.
