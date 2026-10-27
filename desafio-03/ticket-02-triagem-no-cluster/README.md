# Ticket 02: skill de triagem de cluster

Método único de triagem, só leitura, sobre o
[mcp-server-kubernetes](https://github.com/flux159/mcp-server-kubernetes),
executado nos três chamados do laboratório. Depois, o teste de roteamento
entre esta skill e a do Ticket 01, e a medição com e sem skill.

## Onde está cada item pedido

| Entregue | Onde |
|---|---|
| **A skill completa** | [`skill/triagem-de-cluster/`](skill/triagem-de-cluster/): [`SKILL.md`](skill/triagem-de-cluster/SKILL.md) e [`references/armadilhas.md`](skill/triagem-de-cluster/references/armadilhas.md) |
| **A origem da skill** (fluxo, como, ferramenta) | [`origem.md`](origem.md) |
| **Saída real da triagem dos três chamados, com a causa** | [`triagem-dos-chamados.md`](triagem-dos-chamados.md) (resumo e trechos); íntegras em [`execucoes/com-skill/`](execucoes/com-skill/) (`chamado-N.md`, `.trilha.txt`, `.jsonl`) |
| **Matriz de roteamento** (o que disparou, o que errou, o que mudou) | [`roteamento/README.md`](roteamento/README.md); sessões em `roteamento/rodada-1`, `rodada-2` e `rodada-3-reformuladas` |
| **Comparação com e sem skill** (saída, custo, tempo) | [`comparacao-com-e-sem-skill.md`](comparacao-com-e-sem-skill.md); sessões sem skill em [`execucoes/sem-skill/`](execucoes/sem-skill/) |
| **Curadoria** (o que o método fixou × critério do agente; como a skill não escreve no cluster) | [`curadoria.md`](curadoria.md) |

## Ambiente

| Peça | Onde |
|---|---|
| Os três chamados, aplicados com `kubectl apply -f` | [`chamados/`](chamados/) |
| Configuração do MCP (versão fixada, `ALLOW_ONLY_NON_DESTRUCTIVE_TOOLS`, `ALLOWED_TOOLS`, kubeconfig só de leitura) | [`acesso/mcp.json`](acesso/mcp.json), copiada para `/.mcp.json` |
| Identidade só de leitura (SA + ClusterRole `view`) e gerador de kubeconfig | [`acesso/rbac-triagem-leitura.yaml`](acesso/rbac-triagem-leitura.yaml), [`acesso/gera-kubeconfig.sh`](acesso/gera-kubeconfig.sh) |
| Provas do só leitura | [`acesso/prova-tools-list.txt`](acesso/prova-tools-list.txt), [`acesso/prova-auth-can-i.txt`](acesso/prova-auth-can-i.txt) |
| `deny` das ferramentas de escrita no Claude Code | [`/.claude/settings.json`](../../.claude/settings.json) |

Para reproduzir:

```bash
for f in chamados/*.yaml; do kubectl apply -f "$f"; done
bash acesso/gera-kubeconfig.sh kind-kind      # ~/.kube/triagem-leitura.yaml, token de 24h
# abrir o Claude Code na raiz do repo: .mcp.json e a skill já estão lá
```

## Resultado em uma tabela

| Chamado | Causa encontrada | Camada |
|---|---|---|
| 1 `nyx-prod` | `limits.memory: 24Mi` no Deployment, OOMKilled (137) ~1 s após o start; não há LimitRange (o relato "no namespace inteiro" não bate) | Pod |
| 2 `orion-stg` | tag `fake-shop:v1.14.2` inexistente (`NotFound`); revisão 1, sem RS antigo (o relato "não foi substituído" não bate) | Imagem |
| 3 `nyx-stg` | seletor do Service `app: nyx-api` × rótulo do pod `app: nyxapi`; EndpointSlice vazio | Tráfego |

**Agente e modelo:** Claude Code 2.1.311 com Claude Opus 5.5 (`claude-opus-5-5`),
em todas as sessões.
