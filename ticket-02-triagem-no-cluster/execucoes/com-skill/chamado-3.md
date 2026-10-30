**Causa:** o Service `nyx-api` seleciona `app=nyx-api`, mas os pods do kube-news têm o rótulo `app=nyxapi` (sem o hífen). O seletor não casa com nenhum pod, o EndpointSlice fica vazio e o tráfego que chega ao Service não tem para onde ir.

**Camada:** Tráfego

**Evidências** (fonte → o que mostrou):
- `get service nyx-api -o yaml` → `selector: app: nyx-api`, `port: 80`, `targetPort: 8080`.
- `get endpointslices -n nyx-stg` → o slice `nyx-api-47trx` tem `endpoints: null` e `ports: null`. Nenhum endereço, nem mesmo um não pronto.
- `get deployment nyx-api -o yaml` → `selector.matchLabels` e `template.metadata.labels` estão como `app: nyxapi`. Ele roda a imagem `fabricioveronez/kube-news:v1` e está com 2/2 réplicas prontas (`Available=True`).
- `get pods -l app=nyx-api` → não retorna nenhum pod.
- `get pods -l app=nyxapi` → retorna os 2 pods (`trfpw`, `wvt62`), ambos 1/1 Running.

**Contraprova:** o `nyx-postgres` funciona porque o seletor do Service (`app=nyx-postgres`) é idêntico ao rótulo do pod. O slice dele tem o IP `10.244.0.11` com `ready: true` na porta 5432. A porta do `nyx-api` também está certa (`targetPort 8080` = `containerPort 8080`), então o único problema é o rótulo.

**O relato bate com o cluster?** Bate. A aplicação está de pé e saudável, e mesmo assim ninguém chega nela. Só um detalhe: no cluster não existe nenhum objeto chamado `kube-news`. O kube-news roda como Deployment/Service `nyx-api`.

**Correção sugerida (não aplicada):** no manifesto do Service `nyx-api`, trocar o seletor para `app: nyxapi`. O mais certo, porém, é corrigir o Deployment para `app: nyx-api`, que segue o nome do recurso. Nesse caso o Deployment precisa ser recriado, porque `spec.selector` é imutável. Se escolher o caminho do Deployment, troque o rótulo em `selector.matchLabels` e em `template.metadata.labels` ao mesmo tempo.

**Não verificado:**
- Quem devolve o 503. Não olhei Ingress nem Gateway. Um endpoint vazio produz esse sintoma em qualquer proxy que esteja na frente do Service.
- Não testei a chamada de fora, porque isso exigiria port-forward ou exec.

Achados paralelos, que não explicam o chamado:
- `DB_PASSWORD` está em texto puro no Deployment, nos dois workloads.
- Nenhum dos dois tem `resources` definidos.
- O pod `wvt62` reiniciou 1 vez logo depois de subir. Provavelmente o Postgres ainda não estava pronto, mas não investiguei.