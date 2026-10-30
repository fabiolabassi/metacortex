Gerei os manifests em `desafio-03/ticket-04-dashboard-do-cluster/workloads/nyx-dev/` e o `confere.py` (Trivy e regras do padrão) passou com **0 erros e 0 avisos**. Não apliquei nada no cluster.

| Arquivo | Objeto |
|---|---|
| `00-namespace.yaml` | Namespace `nyx-dev`, com Pod Security `restricted` |
| `10-serviceaccount.yaml` | ServiceAccount `nyx-api`, sem token montado |
| `20-configmap.yaml` | `DB_HOST=nyx-db`, `DB_PORT`, `DB_DATABASE`, `DB_USERNAME`, `DB_SSL_REQUIRE` |
| `30-deployment-api.yaml` | Deployment `nyx-api`, 1 réplica, porta 8080 |
| `31-service-api.yaml` | Service `nyx-api` (ClusterIP, porta 80 → 8080) |

Usei o nome `nyx-api` porque é o que já existe em `nyx-stg` e `nyx-prod`.

## A imagem não vai baixar no kind sem um passo seu

O padrão (regra 3.7) não deixa usar imagem pública direto. Por isso o manifesto aponta para `registry.metacortex.io/nyx/kube-news:v1`, a cópia de `fabricioveronez/kube-news:v1` que o Loom publica no registry interno. Seu cluster local é um kind, e provavelmente não alcança esse registry. Se não alcançar, o pod fica em `ImagePullBackOff`. Para rodar localmente sem mudar o manifesto:

```bash
docker tag fabricioveronez/kube-news:v1 registry.metacortex.io/nyx/kube-news:v1
kind load docker-image registry.metacortex.io/nyx/kube-news:v1
```

## O Secret `nyx-db` precisa ter a chave `password`

O Deployment lê `secretKeyRef: {name: nyx-db, key: password}`. Se a chave tiver outro nome no seu Secret, me avise que eu ajusto. Exemplo de criação:

```bash
kubectl -n nyx-dev create secret generic nyx-db --from-literal=password="..."
```

O código tem uma senha padrão (`Pg#123`, em `src/models/post.js:10`). Do jeito que está o manifesto, o pod não sobe sem o Secret em vez de usar essa senha.

## Decisões

- **Probes:** a readiness usa `/ready` e a liveness usa `/health`, as duas definidas em `src/system-life.js`. Nenhuma das duas consulta o banco. Não usei `/` na readiness porque, com o banco fora, a rota `/` derruba o processo inteiro: ela não trata erro e lança uma rejeição não tratada.
- **Migração:** a cada start a aplicação altera o esquema do banco sozinha (`seque.sync({alter: true})`, em `src/models/post.js:59`). Com 1 réplica em dev isso é aceitável. Para stg e prod, o certo é tirar isso num Job separado.
- **Banco fora na subida:** essa alteração do esquema não espera resposta nem trata erro. Se o `nyx-db` não estiver pronto, o processo cai e reinicia até o banco responder. Em dev isso basta.
- **UID e raiz somente leitura:** o usuário da imagem é `node`, e o manifesto força `runAsUser: 10001`. A aplicação não grava em disco (as métricas ficam em memória), então montei só um `emptyDir` em `/tmp`. **Não testei:** o `docker run` precisava de aprovação. Se o pod quebrar, a causa provável é permissão de leitura em `/app`.
- **Recursos** (100m/128Mi de request, 500m/256Mi de limite): são um chute inicial para Node/Express, sem medição.
- **`DB_USERNAME` e `DB_DATABASE` = `kubedevnews`:** copiei dos valores padrão da aplicação e do stg. Confirme se o seu Postgres usa os mesmos.
- **Desligamento (SIGTERM):** a imagem usa `tini`, que repassa o SIGTERM, mas o `node` não trata o sinal e sai na hora. Requisições em andamento são cortadas.

## Problemas encontrados no projeto e no cluster

- A aplicação tem duas rotas de simulação de falha sem autenticação: `PUT /unhealth` e `PUT /unreadyfor/:seconds`. Qualquer um que alcance o Service consegue derrubar o pod.
- Os namespaces `nyx-stg` e `nyx-prod` que já estão no cluster rodam a imagem pública direto e com a senha `Pg#123` em texto no `env` (vi no `nyx-stg`). Isso viola as regras 3.3 e 3.7 e vale um ticket próprio.