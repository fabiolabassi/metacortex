**Causa:** o container `api` do `nyx-api` tem `limits.memory: 24Mi`. O Node do kube-news passa desse limite ao subir e o kernel mata o processo (OOMKilled) cerca de 1 s depois de iniciar, em loop.

**Camada:** Pod

**Evidências** (fonte → o que mostrou):
- `get pods -n nyx-prod` → as 2 réplicas do `nyx-api` estão `OOMKilled`, 0/1, com 6 restarts cada. O `nyx-postgres` está 1/1, sem nenhum restart.
- `describe pod nyx-api-656789474b-9f7q6` → `Reason: OOMKilled` e `Exit Code: 137`, tanto no estado atual quanto no anterior. Entre `Started` e `Finished` passa 1 s (20:42:28 → 20:42:29). `Limits: memory 24Mi`, `Requests: memory 16Mi`. Eventos com `BackOff` (x8).
- `get limitranges,resourcequotas -n nyx-prod` → lista vazia. Não existe nenhum limite aplicado ao namespace.
- `get deployments -o yaml` → o `24Mi` está escrito direto no spec do Deployment `nyx-api` (e no `last-applied-configuration`).

**Contraprova:** o `nyx-postgres`, no mesmo namespace e no mesmo nó, está com `resources: {}`, ou seja, sem limite. Ele está `Running` sem restarts, então o nó e o banco estão bem. Só morre o container que tem o limite de 24Mi.

**O relato bate com o cluster?** Em parte. O sintoma bate. Mas o cluster não mostra limite "no namespace inteiro": não há LimitRange nem ResourceQuota, e o banco nem tem limite. O corte foi feito no manifesto do `nyx-api`. Os dois Deployments também estão na `revision: 1` / `generation: 1`, criados às 23:36Z. Então foram recriados do zero e não há versão anterior para voltar: um `kubectl rollout undo` não resolve.

**Correção sugerida (não aplicada):** no manifesto do `nyx-api` (no repositório ou pipeline do cliente), subir a memória para um valor realista para Node, por exemplo `requests.memory: 128Mi` e `limits.memory: 256Mi`, e reaplicar. Se o objetivo do corte de custos era ter um teto por namespace, isso deve virar uma LimitRange/ResourceQuota com valores medidos, não um número colado no Deployment.

**Não verificado:** não rodei `logs --previous`. Quando o processo morre por OOM em cerca de 1 s, normalmente não sobra log, e o par `137`/`OOMKilled` já fecha a causa. Também não medi o consumo real de memória da API, porque precisaria de metrics-server ou de um teste de carga. Por isso os valores sugeridos são uma estimativa inicial, não uma medida.

Achados paralelos, fora do escopo: `DB_PASSWORD` e `POSTGRES_PASSWORD` estão em texto puro no env, em vez de Secret. A API não tem liveness probe. O banco não tem requests/limits. As imagens vêm de registries públicos, não do registry interno.