O manifesto é reprovado em 11 regras obrigatórias: o script deu 25 ERRO e 7 AVISO. Além disso, ele não roda do jeito que está, e o script não pega esse problema (detalhe no item 3.3). Não alterei o arquivo original. A versão corrigida está em `/tmp/nyx-api-corrigido.yaml` e passou no `confere.py` com **0 erro e 0 aviso**.

## O mais grave, além do que o script aponta

1. **A senha do banco vazou.** `s3nh4-do-banco` está em texto puro no YAML, que já está versionado no repositório. Não basta trocar por `secretKeyRef`: **o time do nyx precisa trocar a senha no Postgres**.
2. **A variável não é a que a aplicação lê.** O kube-news não lê `DATABASE_URL`, e sim `DB_HOST`, `DB_PORT`, `DB_DATABASE`, `DB_USERNAME`, `DB_PASSWORD` e `DB_SSL_REQUIRE` (`src/models/post.js:8-13`). Com o manifesto atual, a app usa os padrões: `localhost` e senha `Pg#123`. Rodei a imagem: ela sobe, falha ao conectar e **cai na hora**, porque o `seque.sync()` não trata o erro (`post.js:59`). Em produção isso vira CrashLoopBackOff.

## Violações por regra

| Regra | Tipo | O que está errado | Como corrigir |
|---|---|---|---|
| 1.1 | obrigatória | Nome `NyxAPI` não está em kebab-case | `nyx-api` |
| 1.3 | obrigatória | Deployment, template e Service só têm `app:`, sem os 4 rótulos `app.kubernetes.io/*` | Colocar `name`, `instance`, `part-of` e `managed-by` nos três |
| 1.4 | obrigatória | O seletor do Service (`app: nyx-api`) não casa com o pod (`app: nyxapi`), então o **Service fica sem endpoint** | Usar o mesmo par `name` + `instance` no `matchLabels` e no `selector`, e `targetPort: http` |
| 1.5 | recomendada | Faltam as anotações `metacortex.io/owner` e `runbook` | Adicionar |
| 2.1 | obrigatória | Sem requests e limits | Os valores de partida são 100m/128Mi e 500m/256Mi. **Não foram medidos**: ajustar depois de medir |
| 2.2 | obrigatória | Sem readiness e sem liveness | Os endpoints existem (`src/system-life.js:11,22`): readiness em `/ready` e liveness em `/health`. Nenhum dos dois depende do banco, e a porta 8080 confere com `server.js:81` |
| 2.3 | obrigatória | `replicas: 1` em prod | `replicas: 2` e um PDB com `minAvailable: 1` (2.5) |
| 2.4 | obrigatória | Sem estratégia declarada (o default é 25%/25%) | `RollingUpdate` com `maxUnavailable: 0` e `maxSurge: 1` |
| 2.6 | — | O código não trata SIGTERM (`server.js`). A imagem tem `tini` (`Entrypoint=[/sbin/tini --]`), então o node morre na hora e corta as requisições em curso | Coloquei um `preStop: sleep 5` para o pod sair dos endpoints antes de morrer. Tratar SIGTERM no código fica como sugestão para o time do nyx |
| 3.1 | obrigatória | Tag `:latest` | Tag fixa. A pública que existe é `fabricioveronez/kube-news:v1`, então usei `registry.metacortex.io/nyx/kube-news:v1`. **Confirmar com o Loom** o nome e a tag espelhados (o original dizia `nyx/api`) |
| 3.2 | obrigatória | Sem securityContext no pod e no container (KSV-0001/03/04/12/14/20/106/118), sem seccomp e sem runAsGroup (avisos) | Pod: `runAsNonRoot`, UID/GID 10001 e `RuntimeDefault`. Container: sem escalada de privilégio, raiz somente leitura e `drop: ALL`. Montar um `emptyDir` em `/tmp` |
| 3.3 | obrigatória | Credencial em `value:` e com o nome errado (ver acima) | Os dados que não são segredo vão para um ConfigMap. `DB_PASSWORD` vem de `secretKeyRef` (Secret `nyx-db`, chave `password`), gerado por comando e fora do repositório |
| 3.4 | obrigatória | O token da ServiceAccount é montado (é o default) | `automountServiceAccountToken: false` no pod e na SA |
| 3.5 | recomendada | Usa a SA `default` | SA própria `nyx-api` |

## O que conferi na imagem

Usei `fabricioveronez/kube-news:v1`, porque a interna não estava acessível. Ela roda como `USER node` (UID 1000), com `CMD node server.js`, `WORKDIR /app` e expõe a porta 8080.

Rodei com `--read-only --user 10001:10001 --cap-drop ALL`: a app chegou a imprimir "Aplicação rodando na porta 8080" e só caiu por falta de banco. Então a raiz somente leitura e o UID 10001 não atrapalham a subida. Não subi um Postgres para testar as probes de ponta a ponta. O container de teste já foi removido.

## YAML corrigido

O arquivo `/tmp/nyx-api-corrigido.yaml` tem SA, ConfigMap, Deployment, Service e PDB. Abaixo, o Deployment, que é onde está a maior parte das mudanças:

```yaml
spec:
  replicas: 2
  strategy: {type: RollingUpdate, rollingUpdate: {maxUnavailable: 0, maxSurge: 1}}
  selector:
    matchLabels: {app.kubernetes.io/name: nyx-api, app.kubernetes.io/instance: nyx-prod}
  template:
    spec:
      serviceAccountName: nyx-api
      automountServiceAccountToken: false
      securityContext: {runAsNonRoot: true, runAsUser: 10001, runAsGroup: 10001, fsGroup: 10001, seccompProfile: {type: RuntimeDefault}}
      containers:
        - name: api
          image: registry.metacortex.io/nyx/kube-news:v1
          ports: [{name: http, containerPort: 8080}]
          envFrom: [{configMapRef: {name: nyx-api}}]   # DB_HOST, DB_PORT, DB_DATABASE, DB_USERNAME, DB_SSL_REQUIRE
          env:
            - name: DB_PASSWORD
              valueFrom: {secretKeyRef: {name: nyx-db, key: password}}
          resources: {requests: {cpu: 100m, memory: 128Mi}, limits: {cpu: 500m, memory: 256Mi}}
          readinessProbe: {httpGet: {path: /ready, port: http}, periodSeconds: 10}
          livenessProbe: {httpGet: {path: /health, port: http}, periodSeconds: 20, failureThreshold: 3}
          lifecycle: {preStop: {exec: {command: ["sleep", "5"]}}}
          securityContext: {allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, privileged: false, capabilities: {drop: ["ALL"]}}
          volumeMounts: [{name: tmp, mountPath: /tmp}]
      volumes: [{name: tmp, emptyDir: {sizeLimit: 64Mi}}]
```

O Secret se cria assim, sem gravar o valor em arquivo:
`kubectl create secret generic nyx-db -n nyx-prod --from-literal=password='<nova-senha>'`

## O time do nyx precisa confirmar

- **Trocar a senha vazada.**
- O nome do time na anotação `metacortex.io/owner` (pus `time-nyx`) e a URL do runbook.
- A imagem e a tag que o Loom espelhou.
- Se o Postgres exige SSL (`DB_SSL_REQUIRE`).
- Os valores de recurso, depois de medir o consumo.
- A queda quando o banco está fora do ar: hoje a app cai em vez de tentar de novo. Precisa de correção no código ou de aceite explícito.