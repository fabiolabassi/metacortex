# Observação das skills durante o projeto

As duas skills (Tickets 01 e 02) estavam instaladas como skills de projeto
(`.claude/skills/`) durante todo o Ticket 04. Cada situação abaixo foi
executada numa **sessão limpa** (`claude -p`), com o pedido escrito como
naquele momento do projeto e **sem citar skill nenhuma**. As respostas
registradas (`.md`) e a tabela abaixo preservam os resultados relevantes.

## O que aconteceu

| # | Momento do projeto | Pedido | Disparou | Devia? | O que aconteceu |
|---|---|---|---|---|---|
| 01 | pré-requisito: subir o kube-news | "gera os manifests do kube-news, cliente nyx, dev" | `padrao-de-manifests` | sim | 5 manifests em `workloads/nyx-dev/`, `confere.py` com 0 erro, probes `/ready` e `/health` lidas do código, sem `/` na readiness porque `/` derruba o processo sem banco. **Mas** a sessão tinha o MCP do cluster e o usou: listou namespaces e **pods de todos os namespaces**, uma leitura que a escrita de manifests não pede |
| 02 | o kube-news não ficou pronto em `nyx-dev` | "o deployment nyx-api não fica pronto" | `triagem-de-cluster` | sim | 4 chamadas MCP, causa no nível do cluster correta ("DNS não resolve `registry.metacortex.io`"), contraprova com o Postgres, nada escrito. A causa real do laboratório (imagem multi-plataforma importada incompleta no kind) estava **fora** do que o cluster mostra; a skill apontou a direção certa ("`kind load` ... `IfNotPresent`") |
| 03 | RBAC de exemplo do dashboard | "escreve uma ClusterRole só de leitura para o dashboard" | `padrao-de-manifests` | **discutível**: é YAML de Kubernetes, mas não é workload | aplicou o padrão, mas **errou a 1.3** (`managed-by: kubectl`) **sem avisar** que o `confere.py` não tinha rodado (sessão sem Bash) |
| 03b | o mesmo pedido, depois de corrigir a skill (v3) | idem | `padrao-de-manifests` | — | abriu com "**Conferência mecânica NÃO feita**", conferiu 1.1, 1.3 e 3.3 à mão, `managed-by: platform` |
| 04 | decisão da ADR-0004 | "diferença prática entre Endpoints e EndpointSlice; qual eu uso?" | nenhuma | não | resposta direta, coincidente com a ADR-0004 (1 turno, US$ 0,12) |

Ao longo do projeto também rodaram as sessões do Ticket 02 (matriz de
roteamento). A rota das duas skills não mudou depois das correções.

## Quais dispararam sozinhas

Todas as que dispararam, dispararam sozinhas (01, 02, 03, 03b). Em nenhum
momento foi preciso chamar uma skill pelo nome.

## Quais precisei chamar manualmente

Nenhuma. O caso mais próximo é o **02**: a triagem achou a causa do cluster,
mas a do laboratório (o containerd do kind com a imagem incompleta) exigiu
`ctr images check` no nó, fora do MCP e fora do método. Isso é correto: a skill
só lê a API do Kubernetes por desenho.

## Quais apareceram onde não deviam

- **03: `padrao-de-manifests` numa ClusterRole.** Disparar não foi o
  problema: a 1.3 vale para todo objeto, e uma ClusterRole da plataforma
  deveria ter os rótulos. O problema foi aplicar o padrão **sem a conferência
  mecânica e sem dizer isso**. Corrigido na skill (v3) e confirmado em 03b.
- **01: a skill de escrita leu o cluster** (pods de todos os namespaces). Não
  foi a outra skill disparando. Foi o agente usando uma ferramenta disponível
  na sessão. A triagem tem a regra "um namespace só"; a de manifests não tinha
  por que tocar o cluster. Não mudei a skill: a correção certa é de ambiente.
  A sessão de escrita não precisa do MCP do cluster, e o `.mcp.json` do
  projeto deveria ser carregado só onde a triagem roda.

## O que precisei reexplicar várias vezes, mesmo com as duas instaladas

- **Que o laboratório espelha imagens** (`registry.metacortex.io/...` não
  existe fora do parque). As duas skills mencionam o Loom, e as sessões 01 e 02
  pararam para explicar que a imagem interna não é acessível, cada uma com a
  própria sugestão (`kind load`, `containerdConfigPatches`). Isso é contexto do
  ambiente, não método. Caberia num `CLAUDE.md` do repositório, não numa skill.
- **O namespace no pedido.** Sem ele, a triagem v2 pergunta (comportamento
  desejado). Na prática, todo pedido de triagem do projeto precisou trazer o
  namespace por extenso.
- **Que o banco é de laboratório** e fica fora dos manifests do cliente. A
  escrita (01) quis saber onde estava o Postgres; foi preciso dizer no pedido
  "o banco é um Service `nyx-db` no mesmo namespace".

## Custo

| Sessão | Tempo | Turnos | Custo |
|---|---|---|---|
| 01 gerar kube-news | 99 s | 32 | US$ 0,66 |
| 02 triagem nyx-dev | 29 s | 9 | US$ 0,23 |
| 03 ClusterRole | 24 s | 5 | US$ 0,18 |
| 04 Endpoints × EndpointSlice | 21 s | 1 | US$ 0,12 |
