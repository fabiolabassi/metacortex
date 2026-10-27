# ADR-0004: Endpoints de Service a partir de EndpointSlice (discovery.k8s.io/v1)

- Status: aceito
- Data: 2026-10-27

## Contexto

O dashboard precisa dizer se um Service tem para onde mandar tráfego. O
Kubernetes guarda isso em dois objetos:

- **`Endpoints` (core/v1):** um objeto por Service. Descontinuado: desde a v1.33,
  o apiserver devolve `Warning: v1 Endpoints is deprecated`. Trunca em 1000
  endereços.
- **`EndpointSlice` (discovery.k8s.io/v1):** GA desde a v1.21. Um ou mais
  slices por Service (rótulo `kubernetes.io/service-name`), com
  `conditions.ready/serving/terminating` por endereço.

No laboratório (kind v1.36):

- `nyx-prod`: o slice do `nyx-api` lista **2 IPs** com o Deployment em 0/2, porque os
  endpoints existem com `ready: false`;
- `nyx-stg`: o slice do `nyx-api` vem com `endpoints: null` e `ports: null`;
- a revisão do padrão (Ticket 01) mostrou que `targetPort` nomeado errado gera
  slice com IPs e porta `<unset>`.

## Decisão

Ler `EndpointSlice` do namespace (uma listagem) e agrupar por
`kubernetes.io/service-name`. Para cada Service:

- `prontos` = endereços com `conditions.ready` verdadeiro ou **ausente**
  (pela API, `ready` nulo deve ser interpretado como pronto);
- `total` = todos os endereços;
- `porta_resolvida` = algum slice com `ports` não nulo.

Os estados de tela são:

- "sem endpoint" (nenhum slice ou nenhum endereço);
- "0/N prontos";
- "N/M prontos";
- "porta não resolvida";
- "sem seletor" (Service sem `selector`, com endpoints manuais);
- "ExternalName".

## Alternativas consideradas

| Alternativa | Ganha | Perde | Por quanto tempo funciona |
|---|---|---|---|
| **EndpointSlice** (escolhida) | API atual; `ready` por endereço (pega o caso `nyx-prod`); porta por slice (pega o `targetPort` errado) | agrupar slices por rótulo; mais de um slice por Service em serviços grandes | é a API que o kube-proxy usa; sem data de remoção |
| **Endpoints** | um objeto por Service, nome igual ao do Service; mais simples de casar | aviso de descontinuado em toda listagem; `notReadyAddresses` separado; trunca em 1000; quando a remoção vier, o dashboard quebra exatamente na informação que justifica sua existência | até a remoção (anunciada como descontinuada na v1.33) |
| **Inferir pelos pods** (seletor do Service × rótulos dos pods prontos) | não depende de nenhum dos dois objetos | reimplementa o controller de endpoints; erra em `targetPort` nomeado, `publishNotReadyAddresses`, pods terminando; não vê endpoints manuais | sempre, mas mostra o que **deveria** ser, não o que **é** |

## Consequências

- (+) O dashboard mostra o mesmo que o kube-proxy enxerga.
- (+) O caso "IPs listados, nenhum pronto" fica visível, e não verde.
- (−) Quem só tem RBAC em `endpoints` (core) e não em `endpointslices` vê
  "sem permissão" nessa coluna. A ClusterRole de exemplo inclui
  `endpointslices`; o `view` padrão do Kubernetes também.
- A seleção do Service (seletor × rótulos) **não** é usada para o veredito. Ela
  aparece só como dica quando não há endpoint ("nenhum pod do namespace casa
  com o seletor").
