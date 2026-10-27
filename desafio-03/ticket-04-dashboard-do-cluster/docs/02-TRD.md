# TRD: `retrato`

Produto no [PRD](01-PRD.md). As decisões estão nos ADRs:

- [0001 stack](adr/0001-stack-python-stdlib-http-e-pagina-unica.md)
- [0002 cliente](adr/0002-cliente-oficial-python.md)
- [0003 atualização](adr/0003-atualizacao-por-intervalo-fixo.md)
- [0004 EndpointSlice](adr/0004-endpointslice.md)
- [0005 fatia](adr/0005-recorte-da-primeira-fatia.md)

## 1. Arquitetura

```
navegador (127.0.0.1:8765)                    processo `python3 -m retrato`
┌─────────────────────────────┐  GET /api/*  ┌──────────────────────────────────┐
│ index.html (JS sem build)   │ ───────────► │ servidor.py  (só do_GET; resto 405)│
│ a cada 10 s: /api/retrato/ns│ ◄─────────── │   └─ retrato.py (monta a tela)    │
└─────────────────────────────┘     JSON     │        └─ leitura.py ── list_* ──►│── apiserver
                                             │           (único módulo com API) │   (kubeconfig,
                                             └──────────────────────────────────┘    contexto corrente)
```

| Módulo | Responsabilidade |
|---|---|
| `leitura.py` | **único** módulo que importa o cliente Kubernetes. Carrega o kubeconfig na subida e expõe só funções `lista_*`. Classifica as falhas |
| `retrato.py` | transforma objetos da API em linhas de tela (motivo do pod, prontos/desejados, estado do endpoint) |
| `servidor.py` | HTTP em `127.0.0.1`; rotas GET; qualquer outro método devolve 405 |
| `static/index.html` | página única: seletor de namespace, busca, quatro seções, faixa de erro |
| `__main__.py` | argumentos (`--porta`, `--intervalo`), subida, mensagem de erro sem traceback |

## 2. API HTTP (só GET)

| Rota | Resposta |
|---|---|
| `GET /` | a página |
| `GET /api/contexto` | `{contexto, cluster, servidor, usuario, namespace_padrao, intervalo_s}`, ou `erro` se o kubeconfig não carregou |
| `GET /api/namespaces` | `{itens: [nomes]}` ou `{erro}` |
| `GET /api/retrato/<ns>` | `{namespace, gerado_em, pods, deployments, services, eventos}`; **cada seção** é `{itens: [...]}` ou `{erro: {tipo, mensagem}}` |

Uma falha numa seção não derruba as outras. As cinco listagens rodam em
paralelo (thread pool), cada uma com o próprio tratamento de erro.

## 3. Classificação de falhas (`leitura.py`)

| Origem | `tipo` | Mensagem na tela |
|---|---|---|
| `urllib3` `MaxRetryError`/`NewConnectionError`/`ProtocolError`, timeout | `cluster_inacessivel` | "O cluster `<servidor>` não respondeu (timeout de N s ou conexão recusada)." |
| `ApiException` 401 | `credencial` | "A credencial do contexto `<ctx>` foi recusada (expirada ou inválida). Renove o login e recarregue." |
| `ApiException` 403 | `sem_permissao` | "Sem permissão para listar `<recurso>` em `<ns>`." |
| `ApiException` 404 em namespace | `nao_encontrado` | "Namespace `<ns>` não existe." |
| outra `ApiException` | `api` | "O apiserver respondeu `<status>`." |
| kubeconfig ausente/inválido na subida | `kubeconfig` | a página abre com a faixa; não há listagem |
| qualquer outra exceção | `interno` | mensagem genérica; o detalhe vai para o log do console, **sem** traceback (só com `--debug`) |

`_request_timeout = (3, 8)` (conexão, leitura). Um cluster fora do ar
responde em ≤ 3 s com `cluster_inacessivel`.

Se `cluster_inacessivel` ou `credencial` aparecer em todas as seções, a página
mostra **uma** faixa global, e não cinco repetidas.

## 4. Regras de exibição

**Pod**
- `estado`: o primeiro motivo de falha encontrado, nesta ordem:
  1. `status.reason` do pod (Evicted...);
  2. `state.waiting.reason` de container (CrashLoopBackOff, ImagePullBackOff, CreateContainerConfigError);
  3. `state.terminated.reason` ≠ Completed;
  4. condição `PodScheduled=False` (Unschedulable);
  5. senão, `status.phase`.
- `ultimo_termino`: `lastState.terminated.reason` + `exitCode` (é onde aparece `OOMKilled 137`).
- `reinicios`: soma de `restartCount`.
- `prontos`: containers `ready` / total.
- `sem_readiness`: algum container sem `readinessProbe` → marca "pronto = processo de pé".

**Deployment**
- `prontos` = `status.readyReplicas` **ou 0 se ausente**; `desejadas` = `spec.replicas` (padrão 1).
- `atualizadas` = `updatedReplicas` ou 0.
- `condicao` = `reason` da condição `Available=False` ou `Progressing=False`.

**Service**
- Tipo, portas (`port→targetPort`), estado do endpoint pela ADR-0004.
- Quando não há endpoint, uma dica: quantos pods do namespace casam com o seletor (0 = seletor não casa).

**Evento**
- Ordenado por `lastTimestamp` (ou `eventTime`, ou `metadata.creationTimestamp`), Warning antes de Normal no mesmo minuto. Limite de 100.
- Colunas: tipo, motivo, objeto (`kind/nome`), mensagem, contagem, há quanto tempo.

**Campo ausente:** toda leitura de campo opcional usa `getattr(..., None) or 0/[]`.
Há teste com objeto sem `readyReplicas`, slice com `endpoints=None` e pod sem
`containerStatuses` (Pending).

## 5. Garantia de só leitura (RNF-01)

1. **Código:** `leitura.py` é o único módulo que importa `kubernetes`. O teste
   `test_somente_leitura` faz parse (AST) de todo `src/` e falha se:
   - outro módulo importar `kubernetes`;
   - houver chamada a método da API que não comece com `list_` ou `read_`;
   - houver referência a `create_`, `patch_`, `replace_`, `delete_`, `connect_` ou `ApiClient.call_api`.
2. **HTTP:** `servidor.py` implementa só `do_GET`. `do_POST`, `do_PUT`,
   `do_PATCH` e `do_DELETE` respondem 405. Há teste.
3. **RBAC:** `deploy/rbac-retrato-leitura.yaml`, uma ClusterRole com `get/list/watch` em
   `namespaces`, `pods`, `services`, `events`, `deployments` e `endpointslices`, mais
   o script para gerar um kubeconfig com ela. Quem quiser a garantia também do
   lado do servidor roda o dashboard com esse kubeconfig.

## 6. Testes

| Nível | O quê |
|---|---|
| unidade | regras de exibição com objetos do cliente oficial (incluindo campos ausentes); classificação de falhas; 405 nos métodos de escrita; teste de AST de só leitura |
| integração | contra o kind: os três chamados do Ticket 02, os workloads do Ticket 01 e os três cenários de falha. Capturas de tela em `evidencias/` |
