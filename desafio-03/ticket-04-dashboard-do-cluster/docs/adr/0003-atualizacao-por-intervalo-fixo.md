# ADR-0003: Atualização por intervalo fixo (10 s), só do namespace aberto

- Status: aceito
- Data: 2026-10-27

## Contexto

A tela mostra **um** namespace por vez: pods, deployments, services, slices e
eventos. A lista de namespaces muda raramente. Quem usa está no meio de um
chamado e quer ver a mudança depois de agir no terminal: segundos, não
milissegundos.

## Decisão

- O navegador pede `GET /api/retrato/<ns>` a cada **10 s**, e o backend faz 5
  listagens em paralelo, só nesse namespace.
- Namespaces a cada 60 s.
- Botão "atualizar agora".
- Pausa quando a aba fica oculta (`visibilitychange`).
- Sem estado no servidor.

## Alternativas consideradas

| Alternativa | Carga no apiserver | Complexidade | Atraso do que aparece |
|---|---|---|---|
| **Intervalo fixo de 10 s** (escolhida) | 5 `list` por 10 s = **0,5 req/s** por tela aberta, só no namespace aberto; zero com a aba oculta | baixa: sem estado no servidor; cada resposta é um retrato completo e coerente | até 10 s (+ latência da listagem) |
| **Sob demanda** (só no botão) | mínima | mínima | ilimitado: o plantonista olha um retrato velho sem perceber, o pior caso para triagem |
| **Watch** (`?watch=true` por recurso) | uma conexão longa por recurso; eventos só quando algo muda (menor carga em regime) | alta: 5 streams, reconexão, `resourceVersion` expirado (**410 Gone** → relistar), cache local por namespace, troca de namespace = derrubar e reabrir 5 watches, empurrar para o navegador (SSE/WebSocket) | ~1 s |
| **Informers do client-go/Python (cache do cluster inteiro)** | lista e observa **todos** os namespaces na subida, o que é pesado em cluster grande e exige permissão de leitura em todo o cluster | alta | ~1 s |

A conta que decide: 0,5 req/s de `list` com `namespace=` é carga desprezível
para o apiserver (um `kubectl get pods -w` de dois plantonistas pesa
parecido). O watch troca essa carga por complexidade que a primeira fatia não
precisa. O informer ainda contradiz o RBAC de quem só pode ler alguns
namespaces (o `platform-ro`).

## Consequências

- (+) Sem estado: reiniciar o dashboard nunca deixa a tela inconsistente.
- (+) Falha num ciclo (timeout, 401) aparece na faixa e se resolve sozinha no próximo, se o ambiente voltar.
- (−) Atraso de até 10 s. O intervalo é configurável (`--intervalo`).
- (−) Eventos muito curtos entre dois ciclos aparecem no ciclo seguinte (eventos persistem ~1 h no cluster), e não somem.
- Revisitar quando houver mais de ~20 telas abertas no mesmo cluster ou necessidade de "ao vivo".
