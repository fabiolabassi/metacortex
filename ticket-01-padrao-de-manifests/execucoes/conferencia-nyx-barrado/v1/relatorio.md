## Conferência do `nyx-api-barrado.yaml` (cliente nyx, kube-news, prod)

Verifiquei de duas formas. O `confere.py` rodou com o Trivy disponível e encontrou **25 erros e 7 avisos** em 11 regras. Depois li o código do kube-news (clonado em `/tmp/kn-conf`, só leitura) para o que o script não decide. O arquivo não foi alterado.

**O mais grave:** a senha do banco está em texto puro, e o nome da variável está errado. A aplicação **não lê `DATABASE_URL`**. Com este manifesto, ela tentaria conectar em `localhost` com a senha padrão `Pg#123` e não subiria. A senha `s3nh4-do-banco` está exposta e precisa ser **trocada**, não só retirada do arquivo.

### Violações por regra

| Regra | Nível | O que está errado | Como corrigir |
|---|---|---|---|
| **1.1** Nome | obrigatória | Deployment `NyxAPI` não está em kebab-case | `nyx-api` |
| **1.3** Rótulos | obrigatória | Deployment, template do pod e Service só têm `app:` (ou nada) | `app.kubernetes.io/{name,instance,part-of,managed-by}` = `nyx-api`, `nyx-prod`, `nyx`, `platform` |
| **1.4** Seletor | obrigatória | Service seleciona `app: nyx-api` e o pod tem `app: nyxapi`. O Service sobe **sem endpoint** | Seletor do Service igual ao `matchLabels` (`name` + `instance`). `targetPort: http` com a porta nomeada no container |
| **2.1** Recursos | obrigatória | Sem requests/limits de CPU e memória (KSV-0011/15/16/18) | Ver o trecho abaixo. Os valores são **chute inicial**, porque não há medição de consumo |
| **2.2** Probes | obrigatória | Sem readiness e sem liveness | Readiness em `/ready` e liveness em `/health`. As duas existem (`src/system-life.js:11,22`) |
| **2.3** Réplicas | obrigatória | `replicas: 1` em prod | `replicas: 2` mais `topologySpreadConstraints` por hostname |
| **2.4** Estratégia | obrigatória | Nenhuma estratégia declarada, então vale o padrão 25%/25% | `RollingUpdate` com `maxUnavailable: 0`, `maxSurge: 1` |
| **3.1** Tag | proibida | `:latest` (KSV-0013) | Usar a tag versionada que o Loom publicou em `registry.metacortex.io/nyx/api`. Confirmar no registry que ela existe |
| **3.2** securityContext | obrigatória | Contexto padrão (KSV-0001/03/04/12/14/20/106/118) | Pod: `runAsNonRoot`, `runAsUser/Group: 10001`, `fsGroup`, `seccompProfile: RuntimeDefault`. Container: `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `drop: [ALL]` |
| **3.3** Segredos | proibida | Senha embutida em `DATABASE_URL` | Variáveis que a app lê. `DB_PASSWORD` vem de `secretKeyRef` e o resto de um ConfigMap |
| **3.4** Token da SA | obrigatória | `automountServiceAccountToken` ausente, então o token é montado | `false` no pod e na SA |
| 1.5 Anotações | recomendada | Sem `metacortex.io/owner` e `/runbook` | Adicionar |
| 2.5 PDB | recomendada | Inexistente (vira exigência com 2 réplicas) | PDB com `minAvailable: 1` |
| 3.5 ServiceAccount | recomendada | Usa a SA `default` | SA dedicada `nyx-api` |

### O que veio da leitura do código

- **Variáveis (3.3):** a app lê `DB_DATABASE`, `DB_USERNAME`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` e `DB_SSL_REQUIRE` (`src/models/post.js:8-13`). Só `DB_PASSWORD` é credencial, e é ela que vai para o Secret.
- **Porta:** `app.listen(8080)` (`src/server.js:81`). O `containerPort: 8080` está correto.
- **Probes (2.2):** `/health` não consulta o banco, então serve para liveness. `/ready` também não consulta o banco: o pod fica pronto mesmo com o Postgres fora. Não é violação, mas vale avisar o cliente.
- **Rotas de falha expostas:** `PUT /unhealth` e `PUT /unreadyfor/:seconds` (`src/system-life.js:30,36`) não exigem autenticação. Qualquer pessoa que alcance o Service derruba um pod. O padrão não cobre isso, mas eu levaria à revisão de segurança: bloquear essas rotas na borda (Ingress ou NetworkPolicy) em prod.
- **Raiz somente leitura (3.2):** a app não grava em disco. As métricas do Prometheus ficam em memória e não há upload. Um `emptyDir` em `/tmp` basta. Ressalva: se a imagem inicia por `npm start`, o npm grava em `~/.npm` e quebra com a raiz somente leitura. O ideal é `node server.js` direto.
- **UID da imagem (3.2):** **não verificado**. O repositório não tem Dockerfile e não inspecionei a imagem interna. Falta rodar `docker image inspect registry.metacortex.io/nyx/api:<tag> --format '{{.Config.User}}'` para confirmar que roda como 10001.
- **SIGTERM (2.6):** `node server.js` não tem handler de SIGTERM e, como PID 1, ignora o sinal. Cada pod espera os 30s inteiros e morre por SIGKILL. Sugiro um `preStop` curto e pedir ao cliente um handler que chame `server.close()`.
- **Migração no start:** `seque.sync({ alter: true })` roda a cada início de pod (`src/models/post.js:59`). Com 2 réplicas, há dois `ALTER` concorrentes no deploy. O time do cliente precisa decidir isso. O ideal é um Job de migração separado.

### Trecho corrigido (só o que muda)

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: nyx-api
  namespace: nyx-prod
  labels: &labels
    app.kubernetes.io/name: nyx-api
    app.kubernetes.io/instance: nyx-prod
    app.kubernetes.io/part-of: nyx
    app.kubernetes.io/managed-by: platform
automountServiceAccountToken: false
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: nyx-api
  namespace: nyx-prod
  labels: *labels
data:
  DB_HOST: pg.nyx-prod.svc
  DB_PORT: "5432"
  DB_DATABASE: nyx
  DB_USERNAME: nyx
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nyx-api
  namespace: nyx-prod
  labels: *labels
  annotations:
    metacortex.io/owner: <time>
    metacortex.io/runbook: https://runbooks.metacortex.io/nyx/api
spec:
  replicas: 2
  strategy:
    type: RollingUpdate
    rollingUpdate: {maxUnavailable: 0, maxSurge: 1}
  selector:
    matchLabels:
      app.kubernetes.io/name: nyx-api
      app.kubernetes.io/instance: nyx-prod
  template:
    metadata:
      labels: *labels
    spec:
      serviceAccountName: nyx-api
      automountServiceAccountToken: false
      terminationGracePeriodSeconds: 30
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001          # confirmar contra o USER da imagem
        runAsGroup: 10001
        fsGroup: 10001
        seccompProfile: {type: RuntimeDefault}
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              app.kubernetes.io/name: nyx-api
              app.kubernetes.io/instance: nyx-prod
      containers:
        - name: api
          image: registry.metacortex.io/nyx/api:<tag-publicada-pelo-loom>
          ports:
            - {name: http, containerPort: 8080}
          envFrom:
            - configMapRef: {name: nyx-api}
          env:
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef: {name: nyx-db, key: password}
          resources:              # chute inicial, ajustar por medição
            requests: {cpu: 100m, memory: 128Mi}
            limits: {cpu: 500m, memory: 256Mi}
          readinessProbe:
            httpGet: {path: /ready, port: http}
            periodSeconds: 10
          livenessProbe:
            httpGet: {path: /health, port: http}
            periodSeconds: 20
            failureThreshold: 3
          lifecycle:
            preStop: {sleep: {seconds: 5}}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            privileged: false
            capabilities: {drop: ["ALL"]}
          volumeMounts:
            - {name: tmp, mountPath: /tmp}
      volumes:
        - name: tmp
          emptyDir: {sizeLimit: 64Mi}
---
apiVersion: v1
kind: Service
metadata:
  name: nyx-api
  namespace: nyx-prod
  labels: *labels
  annotations:
    metacortex.io/owner: <time>
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: nyx-api
    app.kubernetes.io/instance: nyx-prod
  ports:
    - {name: http, port: 80, targetPort: http}
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: nyx-api
  namespace: nyx-prod
  labels: *labels
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: nyx-api
      app.kubernetes.io/instance: nyx-prod
```

As âncoras YAML (`&labels`/`*labels`) só funcionam dentro do mesmo arquivo. Ao separar em um arquivo por objeto, como o padrão pede, repita os rótulos em cada um.

O Secret `nyx-db` não entra no repositório. Depois de trocar a senha, gere-o por comando:

```bash
kubectl -n nyx-prod create secret generic nyx-db --from-literal=password='<nova-senha>' --dry-run=client -o yaml
```

**Falta o cliente confirmar:**
- o UID da imagem e se ela inicia por `node` ou por `npm`;
- a tag publicada pelo Loom;
- os valores de recurso, medidos em regime;
- onde vai rodar o `sequelize.sync`;
- o bloqueio das rotas de falha em prod.

Não rodei o `confere.py` sobre o trecho corrigido.