**Causa:** o Service `nyx-api` não seleciona nenhum pod. Ele procura `app: nyx-api`, mas os pods do kube-news têm o rótulo `app: nyxapi`, sem hífen. Por isso o Service não tem nenhum endpoint, e quem está na frente dele não tem para onde mandar o tráfego.

**Camada:** Tráfego

**Evidências** (fonte → o que mostrou):
- `get services -n nyx-stg` → não existe Service chamado `kube-news`. A aplicação kube-news (imagem `fabricioveronez/kube-news:v1`) roda no Deployment `nyx-api`, atrás do Service `nyx-api`, que usa `selector: app: nyx-api`, `port 80 → targetPort 8080`.
- `get endpointslices` → o slice `nyx-api-47trx` está com `endpoints: null` e `ports: null`, ou seja, nenhum endereço.
- `get deployment nyx-api -o yaml` → `selector.matchLabels` e `template.metadata.labels` estão como `app: nyxapi`. O Deployment está 2/2 pronto, `Available=True`.
- `get pods -l app=nyx-api` → nenhum pod. `get pods -l app=nyxapi` → os dois pods (`trfpw` e `wvt62`), ambos 1/1 Running.

**Contraprova:** o `nyx-postgres` funciona porque o seletor do Service (`app: nyx-postgres`) é igual ao rótulo dos pods. O EndpointSlice dele tem `10.244.0.11` com `ready: true`.

**O relato bate com o cluster?** Em parte. A aplicação está mesmo de pé e saudável (2/2 prontos, probes passando). Mas o nome "kube-news" é o da imagem: no cluster, o Deployment e o Service se chamam `nyx-api`. O 503 é o que se espera quando o Service não tem endpoint, em qualquer proxy que esteja na frente.

**Correção sugerida (não aplicada):** no manifesto do Service `nyx-api`, trocar o seletor para `app: nyxapi`. A forma mais correta, porém, é corrigir o Deployment para `app: nyx-api`, que segue o padrão de nomes dos outros objetos. Nesse caso é preciso recriar o Deployment, porque `spec.selector` não pode ser alterado depois de criado.

**Não verificado:**
- Não procurei Ingress/Gateway no namespace, então não confirmei quem devolve o 503. A causa já está explicada sem isso.
- Não testei a requisição de ponta a ponta, porque isso exigiria port-forward ou exec.

Achados paralelos, que não explicam o chamado:
- A senha do banco `DB_PASSWORD`/`POSTGRES_PASSWORD` está em texto puro no manifesto, e não num Secret.
- Os dois Deployments estão sem `resources`.
- O pod `nyx-api-...-wvt62` reiniciou 1 vez no início. Provavelmente o banco ainda estava subindo, mas não investiguei.