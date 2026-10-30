Os manifests do fake-shop para orion/prod estão em `desafio-03/ticket-01-padrao-de-manifests/execucoes/escrita-fake-shop/manifests/`. O `confere.py` deu **0 erro e 0 aviso** nos 8 objetos, com o Trivy incluído. Não apliquei nada no cluster.

| Arquivo | Objeto |
|---|---|
| `00-namespace.yaml` | Namespace `orion-prod` (Pod Security `restricted`) |
| `10-serviceaccount.yaml` | SA `orion-fake-shop` (aplicação) |
| `11-serviceaccount-migracao.yaml` | SA `orion-fake-shop-migracao` (Job) |
| `20-configmap.yaml` | `DB_HOST`, `DB_PORT`, `DB_NAME`, `FLASK_APP`, `PROMETHEUS_MULTIPROC_DIR` |
| `25-job-fake-shop-migracao.yaml` | Job que roda `flask db upgrade` |
| `30-deployment-fake-shop.yaml` | Deployment, 2 réplicas |
| `31-service-fake-shop.yaml` | Service ClusterIP 80 → `http` (5000) |
| `32-pdb-fake-shop.yaml` | PDB `minAvailable: 1` |

**O que o código e a imagem mostram:** o processo escuta na porta 5000 (`entrypoint.sh`), roda como o usuário `app`, UID 10001 (confere com o padrão), e a aplicação lê `DB_HOST/USER/PASSWORD/NAME/PORT` (`src/index.py:22-26`). Não existe rota de saúde. O `/metrics` existe e não usa o banco.

Subi a imagem localmente com root read-only, UID 10001 e todas as capabilities removidas. O gunicorn iniciou os 2 workers e o `/metrics` respondeu 200 sem banco. Não cheguei a testar a raiz `/`, a migração contra um banco real nem o tempo de parada com SIGTERM.

## Decisões

1. **Migração num Job separado.** Com 2 réplicas e `maxSurge: 1`, deixar a migração no entrypoint faria as réplicas rodarem a migração ao mesmo tempo. O Deployment troca o `entrypoint.sh` por `python -m gunicorn ...`. Com isso o gunicorn passa a receber o SIGTERM diretamente, o que o `bash` do entrypoint não faz. O Job precisa terminar **antes** do Deployment (o comando `kubectl wait` está no cabeçalho do arquivo). Como o template de um Job não pode ser alterado, a cada nova tag é preciso apagar o Job anterior, ou transformá-lo em hook PreSync/pre-upgrade no pipeline.
2. **Probes sem rota de saúde.** Não criei rota nova:
   - **readiness em `/`:** a página lista os produtos do banco. Sem banco ou sem esquema ela dá erro, e o pod só sai do Service, sem reiniciar.
   - **liveness em `/metrics`:** não depende do banco e só prova que o gunicorn responde.
   - **Dívida:** a aplicação deveria expor `/health` e `/ready`.
3. **Senha fora do manifesto.** `DB_USER` e `DB_PASSWORD` vêm do Secret `orion-db` via `secretKeyRef`. O Secret não é versionado; o comando que o cria está no fim do `20-configmap.yaml`. Fica sem `optional`, então o pod não sobe sem o Secret.
4. **Root read-only.** Montei `emptyDir` em `/tmp` (usado pelo gunicorn) e outro em `/tmp/metrics`. Os dois são necessários porque o primeiro esconde o diretório que vem pronto na imagem. O Job também precisa do `/tmp/metrics`, porque o `index.py` liga as métricas assim que é carregado.
5. **Recursos são um chute inicial.** 100m/192Mi de request e 500m/384Mi de limit para 2 workers. Ajustar pela regra de 1,5x a 2x o consumo quando houver medição.
6. **`terminationGracePeriodSeconds: 40`:** o gunicorn espera os workers por até 30s.
7. **PostgreSQL fora destes manifests.** Parti do princípio de que o banco de prod é gerenciado ou externo.

## O que o time-orion precisa confirmar ou fazer

- **Host do banco:** `DB_HOST` está com um valor provisório, marcado com TODO.
- **Criar o Secret** `orion-db` com as chaves `username` e `password`.
- **Espelhar a imagem:** `fabricioveronez/fake-shop:v1` precisa ser espelhada pelo Loom como `registry.metacortex.io/orion/fake-shop:v1`. Imagem pública não entra direto, e os manifests já apontam para o registry interno.
- **Owner e runbook:** usei `time-orion` e `https://runbooks.metacortex.io/orion/fake-shop` por analogia com o nyx. Os dois são suposições.
- **Problemas no código que o manifesto não resolve:**
  - **Senha padrão no código:** `DB_PASSWORD` cai em `'Pg1234'` se a variável faltar (`index.py:24`).
  - **Chave de sessão fixa:** `app.secret_key = 'supersecretkey'` está no código (`index.py:16`).
  - **Dados de cartão no banco:** o checkout grava o número do cartão e o CVV (`index.py:107-110`). É um problema sério de conformidade (PCI) para levar ao cliente.

O clone do projeto ficou em `/tmp/fake-shop-src`. Pode apagar.