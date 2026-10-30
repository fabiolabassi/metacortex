**Use EndpointSlice.** A API `Endpoints` (core/v1) foi marcada como deprecated no Kubernetes 1.33 (o `kubectl` passa a mostrar warning). Ela continua funcionando, mas não é onde o ecossistema está investindo. Além disso, ela esconde coisas que um dashboard precisa mostrar.

## Diferenças práticas

| | `Endpoints` | `EndpointSlice` |
|---|---|---|
| Objetos por Service | 1, com o mesmo nome do Service | N fatias, ligadas pelo rótulo `kubernetes.io/service-name` |
| Limite | Trunca em 1000 endereços (anotação `endpoints.kubernetes.io/over-capacity: truncated`) | 100 por fatia por padrão, cria quantas fatias forem necessárias |
| Estado do endpoint | Só `addresses` (pronto) e `notReadyAddresses` | `conditions.ready`, `serving` e `terminating` |
| Dual-stack | Só uma família de IP | Uma fatia por `addressType` (IPv4/IPv6) |
| Status da API | Deprecated | Atual, é o que o kube-proxy usa |

O ganho mais visível para um dashboard é `terminating`. Com `Endpoints`, um pod em rollout aparece só como "not ready". Com `EndpointSlice` dá para distinguir "não ficou pronto" (problema de probe) de "está saindo" (rollout normal).

## Como contar endpoints prontos corretamente

1. **Liste por rótulo, não por nome:**
   ```
   kubectl get endpointslices -n <ns> -l kubernetes.io/service-name=<svc> -o json
   ```
2. **Junte todas as fatias.** Se ler só a primeira, a contagem sai errada em Services maiores.
3. **Conte quem tem `conditions.ready != false`.** Pela especificação, `ready` ausente (nil) deve ser tratado como pronto.
4. **Remova duplicados pelo endereço.** Durante atualizações, o mesmo endpoint pode aparecer em duas fatias por um instante, e a documentação diz que o cliente precisa lidar com isso.

Por exemplo:
```bash
kubectl get endpointslices -n prod -l kubernetes.io/service-name=api -o json \
  | jq '[.items[].endpoints[]? | select(.conditions.ready != false) | .addresses[]] | unique | length'
```

## Casos que o dashboard deve tratar à parte

Sem isso você vai ter falso alarme de "sem endpoint":

- **Service `type: ExternalName`:** nunca tem endpoints. Mostre "N/A", não "0".
- **Service sem `selector`:** o controller não cria fatias. Se alguém criou `Endpoints` manualmente, o controller de mirroring copia para uma EndpointSlice. Se não criou, não existe nada, e isso pode ser intencional.
- **Nenhuma fatia encontrada × fatias sem nenhum endpoint pronto:** são situações diferentes. A primeira costuma indicar seletor que não casa com nenhum pod. A segunda indica pods existentes que não passam na readiness. Vale mostrar as duas de forma distinta, porque o diagnóstico muda.

## RBAC

A service account do dashboard precisa de `get`/`list`/`watch` em `endpointslices` no grupo `discovery.k8s.io`, que não é o grupo core `""` usado por `endpoints`. É um erro comum ao migrar.

Se o dashboard ficar atualizando em tempo real, prefira um watch/informer sobre EndpointSlices filtrado pelo rótulo em vez de polling. Bibliotecas como client-go e o client Python do Kubernetes já oferecem isso.