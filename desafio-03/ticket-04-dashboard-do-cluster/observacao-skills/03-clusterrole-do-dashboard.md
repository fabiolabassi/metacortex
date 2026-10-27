Segue a ClusterRole, escrita conforme o Padrão de Manifests da Metacortex:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: dashboard-leitura
  labels:
    app.kubernetes.io/name: dashboard
    app.kubernetes.io/instance: dashboard-local
    app.kubernetes.io/part-of: metacortex
    app.kubernetes.io/managed-by: kubectl
rules:
  - apiGroups: [""]
    resources: ["namespaces", "pods", "services", "events"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["discovery.k8s.io"]
    resources: ["endpointslices"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["events.k8s.io"]
    resources: ["events"]
    verbs: ["get", "list", "watch"]
```

**Decisões:**

- **Permissões (`verbs`):** o dashboard só recebe `get`, `list` e `watch`. Incluí `watch` porque dashboards costumam acompanhar mudanças em tempo real. Se o seu só faz polling, dá para tirar.
- **Os dois grupos de `events`:** `events` aparece no grupo core (`""`) e em `events.k8s.io`. As duas APIs mostram os mesmos objetos, mas o cliente consulta só uma delas. Mantive as duas para funcionar com qualquer cliente. Se você souber qual API o dashboard usa, pode remover a outra.
- **O que ficou de fora:** `secrets`, `configmaps`, `pods/log` e `pods/exec`. Nenhum deles estava na sua lista, e `secrets` ou `pods/exec` numa role "de leitura" seriam um vazamento de credenciais.
- **Rótulos (regra 1.3):** a ClusterRole não tem namespace, então a regra 1.2 não se aplica. Por isso usei `instance: dashboard-local` no lugar do nome do namespace. Também coloquei `part-of: metacortex`; se o dashboard pertencer a um cliente específico, troque pelo nome dele.
- **Anotações (regra 1.5, recomendada):** deixei de fora `metacortex.io/owner` e `metacortex.io/runbook` porque não sei quem é o dono nem qual é o runbook. Sem elas, o script de conferência vai mostrar um AVISO.

**Não verificado:** nesta sessão não tenho como executar comandos, então não rodei o `confere.py` neste YAML. Para conferir:

```bash
python3 .claude/skills/padrao-de-manifests/scripts/confere.py <arquivo>.yaml
```

**Falta o binding:** a ClusterRole sozinha não dá acesso a ninguém. Como o dashboard roda localmente, o mais provável é que ele use o seu kubeconfig, e aí o seu usuário provavelmente já tem mais permissões que essa role. Para o dashboard rodar só com leitura, crie uma ServiceAccount dedicada (regra 3.5) e ligue a role a ela com uma `ClusterRoleBinding`. Se quiser, eu escrevo os dois.