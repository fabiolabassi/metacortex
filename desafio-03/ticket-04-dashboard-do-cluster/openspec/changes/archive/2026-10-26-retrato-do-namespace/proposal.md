## Why

O plantonista gasta os primeiros minutos de cada chamado montando o retrato
de um namespace com 6 a 10 comandos no terminal. Contexto em
`docs/00-brainstorm.md` e `docs/01-PRD.md`.

## What Changes

- Nova aplicação local `retrato` (Python, página web em `127.0.0.1`) que lê o contexto corrente do kubeconfig na subida.
- Tela com namespaces, pods (estado, reinícios, motivo), deployments (prontos/desejados), services (com/sem endpoint, via EndpointSlice) e eventos do namespace selecionado.
- Filtro por namespace, busca por nome, atualização a cada 10 s.
- Tratamento por seção de cluster inacessível, credencial recusada e permissão negada.
- Garantia de só leitura no código, no servidor HTTP e numa ClusterRole de exemplo.

## Capabilities

### New Capabilities
- `retrato-do-namespace`: o que a tela mostra e como cada campo é derivado da API, incluindo campos ausentes e o limite de "pronto".
- `falhas-de-ambiente`: comportamento com cluster que não responde, credencial expirada e permissão negada por recurso.
- `somente-leitura`: a garantia de que nenhuma escrita é feita, verificável em código, HTTP e RBAC.

### Modified Capabilities
<!-- nenhuma: projeto novo -->

## Impact

- Código novo em `src/retrato/`, testes em `tests/`, RBAC de exemplo em `deploy/`.
- Dependência: `kubernetes==37.0.1` (cliente oficial).
- Decisões em `docs/02-TRD.md` e `docs/adr/0001..0005`.
