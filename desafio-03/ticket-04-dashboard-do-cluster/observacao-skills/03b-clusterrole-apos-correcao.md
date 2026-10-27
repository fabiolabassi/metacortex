**Conferência mecânica NÃO feita.** Nesta sessão não tenho como executar comandos, então não rodei o `confere.py`. Conferi à mão as regras 1.1, 1.3 e 3.3 do padrão.

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: dashboard-leitura
  labels:
    app.kubernetes.io/name: dashboard
    app.kubernetes.io/instance: <cliente>-<amb>
    app.kubernetes.io/part-of: <cliente>
    app.kubernetes.io/managed-by: platform
  annotations:
    metacortex.io/owner: <time>
    metacortex.io/runbook: <url-do-runbook>
rules:
  # namespaces, pods, services e events (API core)
  - apiGroups: [""]
    resources: ["namespaces", "pods", "services", "events"]
    verbs: ["get", "list", "watch"]
  # deployments
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list", "watch"]
  # endpointslices
  - apiGroups: ["discovery.k8s.io"]
    resources: ["endpointslices"]
    verbs: ["get", "list", "watch"]
  # events pela API nova (kubectl events e clientes recentes usam esta)
  - apiGroups: ["events.k8s.io"]
    resources: ["events"]
    verbs: ["get", "list", "watch"]
```

**Conferência manual**
- **1.1:** o nome `dashboard-leitura` está em kebab-case e tem menos de 63 caracteres.
- **1.2:** não se aplica, porque ClusterRole vale para o cluster inteiro e não tem namespace.
- **1.3:** os quatro rótulos estão presentes e `managed-by: platform` está entre os valores aceitos. Falta você preencher `<cliente>`, `<amb>` e `<time>`, porque não sei de qual cliente é esse dashboard.
- **3.3:** nenhum segredo aparece no YAML. A role também não dá acesso a `secrets`, e isso foi intencional.

**Decisões**
- **Só leitura:** os verbos são apenas `get`, `list` e `watch`. Não incluí `pods/log` nem `pods/exec` porque não foram pedidos. Se o dashboard for mostrar logs, acrescente uma regra para `pods/log` com o verbo `get`.
- **Events:** coloquei events nos dois grupos de API, `""` e `events.k8s.io`. Assim a role funciona qualquer que seja a API que o cliente do dashboard usa. Se souber qual é, pode tirar a outra.
- **A role sozinha não dá acesso:** ela só tem efeito quando ligada a alguém por uma `ClusterRoleBinding`. Rodando localmente, o dashboard usa o kubeconfig, e com as suas credenciais de admin ele enxerga tudo, com ou sem essa role. Para que ela realmente limite o acesso, o dashboard precisa usar uma ServiceAccount própria. O token sai de `kubectl create token <sa> -n <ns>` e a ServiceAccount precisa da binding. Antes de usar, dá para testar com `kubectl auth can-i --list --as=system:serviceaccount:<ns>:<sa>`.

Se você me passar o cliente e o namespace da ServiceAccount, escrevo a ServiceAccount e a ClusterRoleBinding no mesmo padrão. Recomendo rodar o `confere.py` nos arquivos antes de aplicar.