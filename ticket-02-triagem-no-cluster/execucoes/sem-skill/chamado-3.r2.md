**Causa:** o Service `nyx-api` não encontra nenhum pod porque o rótulo dos pods não bate com o seletor do Service. Falta um hífen.

| Recurso | Valor |
|---|---|
| Seletor do `service/nyx-api` | `app: nyx-api` |
| Rótulo dos pods `nyx-api-7f4487c6ff-*` | `app: nyxapi` |

**O que comprova:**
- `endpoints/nyx-api` está como `<none>`. O Service tem um ClusterIP, mas nenhum backend para onde mandar o tráfego. Por isso quem chama de fora recebe 503: o proxy ou gateway na frente não acha nenhum endpoint disponível.
- Os dois pods do `nyx-api` estão `Running` e `Ready 1/1`, e as probes `/health` e `/ready` na porta 8080 passam. A aplicação está saudável, como o cliente disse.
- Para comparar, o `nyx-postgres` tem endpoint (`10.244.0.11:5432`) porque o rótulo dele bate com o seletor. Isso mostra que o problema está só no par Service/pods da API.

**Correção:** alinhar os dois lados. O mais limpo é corrigir o template do Deployment para `app: nyx-api`. Se o `spec.selector` do Deployment também estiver como `nyxapi`, ele não pode ser alterado no lugar, porque o seletor do Deployment é imutável. Aí é preciso recriar o Deployment. Outra saída mais rápida é mudar o seletor do Service para `app: nyxapi`. O `targetPort: 8080` está certo e coincide com a porta do container. Não alterei nada no cluster, só fiz leituras.

**Duas observações à parte:**
1. Não existe nenhum Ingress no cluster, nem no `nyx-stg` nem em outros namespaces. Vale confirmar com o cliente por onde o tráfego externo entra (Gateway API, port-forward, LoadBalancer de outro lugar) para validar a correção de ponta a ponta.
2. A senha do banco (`DB_PASSWORD`) está em texto puro no `env` do pod. Isso não causa o 503, mas deveria ir para um Secret.