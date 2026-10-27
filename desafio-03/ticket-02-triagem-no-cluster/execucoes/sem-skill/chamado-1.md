**Causa: a API morre por falta de memória (OOMKilled) logo ao iniciar.** O limite de memória do container caiu para **24Mi**, e um processo Node.js como o kube-news precisa de bem mais que isso só para subir.

**O que encontrei**

- **Estado dos pods:** as duas réplicas de `nyx-api` estão `OOMKilled` com exit code 137, já com 5 restarts em cerca de 4 minutos, e entraram em `BackOff`. O Deployment está `MinimumReplicasUnavailable`, ou seja, **a API está fora do ar**, não só instável.
- **Momento da morte:** cada execução dura cerca de 1 segundo (por exemplo, `Started 20:39:38`, `Finished 20:39:39`). O kernel mata o processo durante a inicialização, antes de ele atender qualquer requisição. Por isso também não há logs do container anterior.
- **Recursos configurados no Deployment `nyx-api`:**
  ```yaml
  limits:   { cpu: 200m, memory: 24Mi }
  requests: { cpu: 50m,  memory: 16Mi }
  ```
- **O Postgres está bem:** `nyx-postgres` está `Running` com 0 restarts, porque não tem `resources` definido e, portanto, não tem limite.

**O cenário relatado não bate com o cluster**

O chamado diz que o corte mudou os limites "do namespace inteiro de uma vez", mas o cluster não mostra isso:
- Não existe `LimitRange` nem `ResourceQuota` em `nyx-prod`.
- O limite de 24Mi está escrito direto no Deployment `nyx-api`.
- O Postgres nem tem limites.

Então o corte foi aplicado no manifest da API, não numa política do namespace. Isso importa para a correção: mexer em `LimitRange` não resolve nada. É preciso corrigir o Deployment, e também a origem dele (repositório, GitOps ou Helm), senão o próximo deploy volta para 24Mi. Vale confirmar com o cliente quem aplicou o corte e onde.

**Correção sugerida** (não apliquei nada, só fiz leitura)

Subir a memória da API para algo realista, como `requests.memory: 128Mi` e `limits.memory: 256Mi`, e depois ajustar pelo consumo real com `kubectl top pod`. Para quem quer economizar, a CPU é o lugar mais seguro para cortar: com CPU baixa o processo fica lento, mas não morre.

**Problemas paralelos que vi durante a triagem**

- `DB_PASSWORD` está em texto puro no `env` dos dois Deployments e na anotação `last-applied-configuration`. Deveria vir de um `Secret`.
- A API não tem `livenessProbe` e o Postgres não tem probe nenhuma. Os restarts de agora vêm só do OOM, não de probe.