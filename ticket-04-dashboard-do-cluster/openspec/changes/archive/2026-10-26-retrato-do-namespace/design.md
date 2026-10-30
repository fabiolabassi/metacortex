## Context

Projeto novo. Motivação em `proposal.md`, requisitos em `specs/`. As decisões
estruturais estão nos ADRs (`docs/adr/0001..0005`) e o detalhamento em
`docs/02-TRD.md`; aqui fica só o que guia a implementação.

## Goals / Non-Goals

**Goals:**
- Um único ponto de contato com a API (`leitura.py`), verificável por teste.
- Seções independentes: a falha de uma não apaga as outras.
- Regras de exibição como funções puras sobre os modelos do cliente, testáveis sem cluster.

**Non-Goals:**
- Cache, watch ou estado no servidor (ADR-0003).
- Qualquer tela além do retrato de um namespace (ADR-0005).

## Decisions

1. **Cinco listagens em paralelo por retrato** (`ThreadPoolExecutor`, 5
   workers). Alternativa descartada: sequencial, porque somaria os timeouts
   (até 5 × 3 s com o cluster fora).
2. **Erro como dado**: cada seção devolve `{itens}` ou `{erro: {tipo, mensagem}}`,
   e o frontend decide se mostra faixa global (mesmo erro em todas) ou local.
   Alternativa descartada: HTTP 5xx na rota, porque perderia as seções que funcionaram.
3. **Regras de exibição sobre os modelos do cliente** (`V1Pod`,
   `V1Deployment`...), não sobre dicts. Os testes constroem os modelos com
   campos ausentes, do mesmo jeito que o cliente os desserializa.
4. **Frontend sem framework**: `fetch` + montagem de `<tbody>` por
   `textContent` (nunca `innerHTML` com dado da API, para não haver injeção
   de HTML vinda de nome de objeto ou mensagem de evento).

## Risks / Trade-offs

- [Muitos eventos num namespace] → limite de 100, mais recentes primeiro.
- [Timeout curto em cluster lento e saudável] → `(3, 8)` s: conexão curta, leitura mais folgada; configurável.
- [Token de `exec` plugin expira com a página aberta] → o cliente renova pelo plugin a cada chamada; se não renovar, cai em 401 e mostra a faixa.

## Migration Plan

Ferramenta nova: `pip install -r requirements.txt` e `python3 -m retrato`.
