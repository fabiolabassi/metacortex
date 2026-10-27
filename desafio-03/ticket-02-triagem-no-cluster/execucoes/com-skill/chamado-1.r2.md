A API está sendo morta por falta de memória (OOMKilled). O limite de memória do container é de **24Mi**, pequeno demais para o kube-news, que não consegue nem terminar de subir.

**Causa:** o próprio Deployment `nyx-api` define `resources.limits.memory: 24Mi`. O kernel mata o processo cerca de 5 s depois de cada start, e o pod entra em CrashLoop.
**Camada:** Pod

**Evidências** (fonte → o que mostrou):
- `get pods -n nyx-prod` → os 2 pods `nyx-api` estão em `CrashLoopBackOff` com 7 restarts cada. `nyx-postgres` está `Running` com 0 restarts.
- `describe pod nyx-api-656789474b-9f7q6` → `Last State: Terminated`, `Reason: OOMKilled`, `Exit Code: 137`. Subiu às 20:47:43 e morreu às 20:47:48. `Limits: memory 24Mi`, `Requests: memory 16Mi`.
- `logs --previous` → vazio. É o esperado quando o kernel mata o processo durante o start; a evidência é o `OOMKilled` com código 137.
- `get limitranges,resourcequotas -n nyx-prod` → não existe nenhum. O limite não vem do namespace.
- `get deployment nyx-api -o yaml` → `limits.memory: 24Mi` está escrito na spec do container, e também no `last-applied-configuration`.
- Deployment `nyx-api` → `Available=False` e `ProgressDeadlineExceeded`.

**Contraprova:** o `nyx-postgres` roda no mesmo namespace e no mesmo nó sem nenhum restart. Ele tem `resources: {}`, ou seja, nenhum limite de memória. Como não há LimitRange para impor um padrão, ele não tem teto e não é morto.

**O relato bate com o cluster?** Só em parte:
- **"Mudou os limites do namespace inteiro":** não é o que o cluster mostra. Não há LimitRange nem ResourceQuota, e só a API tem limite; o banco não tem nenhum. O corte foi aplicado direto no manifesto do Deployment da API. Para quem for corrigir, isso significa que mexer no namespace não resolve: a mudança é no manifesto.
- **"Depois do corte":** no cluster, o Deployment está na revisão 1, com `generation: 1`, e foi criado há cerca de 14 min. Não existe versão anterior com o limite antigo, então um `kubectl rollout undo` não tem para onde voltar. O valor bom precisa vir do repositório ou do histórico do pipeline.

**Correção sugerida (não aplicada):** no manifesto do Deployment `nyx-api`, subir `limits.memory` para um valor que o Node.js do kube-news aguente, por exemplo `256Mi` com `requests.memory: 128Mi`. Depois disso, ajustar o valor pelo consumo real observado. Aplicar pelo pipeline ou repositório que gerencia o `nyx-prod`, não com edição direta no cluster.

**Não verificado:**
- O consumo real de memória da API. Não há métrica disponível aqui, e medir exigiria o pod de pé.
- Qual era o limite antes do corte. Essa informação não está no cluster.

Achados paralelos, sem investigação:
- `DB_PASSWORD`/`POSTGRES_PASSWORD` (`Pg#123`) estão em texto puro no `env` dos dois Deployments, em vez de virem de um Secret.
- A API tem só readiness probe, sem liveness.
- O banco roda sem requests/limits.