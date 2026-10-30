## Causa: o Service `nyx-api` não aponta para nenhum pod

O Service e o Deployment usam rótulos diferentes. Falta um hífen:

| Recurso | Seletor / rótulo |
|---|---|
| `service/nyx-api` (selector) | `app: nyx-api` |
| `deployment/nyx-api` (rótulos dos pods) | `app: nyxapi` |

O selector do Service não casa com nenhum pod, então o Endpoints dele está vazio:

```
nyx-api        <none>             ← nenhum backend
nyx-postgres   10.244.0.11:5432   ← ok, rótulos batem
```

A aplicação de fato está saudável: os 2 pods estão `1/1 Running`, as readiness e liveness probes passam e a porta está certa (`targetPort: 8080` igual a `containerPort: 8080`). O problema é que o tráfego chega ao Service e não tem para onde ir. Com zero endpoints, o proxy de borda responde **503**, a resposta padrão quando não há backend disponível.

## Correção sugerida

Alinhe os rótulos. Não alterei nada no cluster. Recomendo corrigir o **Service** para `app: nyxapi` no manifest e reaplicar, porque é a mudança menos invasiva e não recria pods:

```yaml
spec:
  selector:
    app: nyxapi
```

Também dá para corrigir o lado do Deployment, que é o nome mais coerente (`nyx-api`). Nesse caso você precisa mudar o `spec.selector` e o `template.metadata.labels`. Como o `spec.selector` de um Deployment é imutável, o Deployment teria que ser apagado e recriado.

Depois da correção, `kubectl get endpoints nyx-api -n nyx-stg` deve listar `10.244.0.9:8080` e `10.244.0.14:8080`.

## Outras coisas que vi

- **Não há Ingress em nenhum namespace.** Se o acesso externo passa por Gateway API (HTTPRoute) ou outro proxy, ainda vale confirmar que ele aponta para `nyx-api:80`. Mesmo assim, o 503 se explica pelos endpoints vazios.
- **O pod `wvt62` reiniciou uma vez logo no início**, com exit 1. O mais provável é que o Postgres ainda não estivesse pronto quando a aplicação subiu. Depois disso ele ficou estável, e isso não tem relação com o 503.
- **A senha do banco está em texto puro na env** (`DB_PASSWORD: Pg#123`). Ela deveria ir para um Secret. Não tem relação com o chamado, mas vale registrar.