# Origem da skill `triagem-de-cluster`

**Agente:** Claude Code 2.1.311. **Modelo:** Claude Opus 5.5 (`claude-opus-5-5`).
**Acesso ao cluster:** mcp-server-kubernetes 4.1.9. **Cluster:** kind, Kubernetes v1.36.1.
**Ferramenta de empacotamento:** a própria sessão do Claude Code, com as
ferramentas de edição do agente.

## Fluxo que deu origem

### 1. Ambiente e acesso só de leitura

Os três chamados foram aplicados no kind com `kubectl apply -f` (`chamados/`).
Depois de ~4 minutos, o cluster estava no estado de cada defeito:

- `nyx-prod`: `nyx-api` em `OOMKilled`/`CrashLoopBackOff`, 0/2;
- `orion-stg`: `orion-web` em `ImagePullBackOff`, 0/3;
- `nyx-stg`: `nyx-api` 2/2 Running, EndpointSlice `<unset>`.

Antes de qualquer triagem, foi montado o acesso. O detalhe está em
`curadoria.md` §2. O ponto que mudou o plano: o modo
`ALLOW_ONLY_NON_DESTRUCTIVE_TOOLS=true`, pedido no enunciado, **ainda expõe
`kubectl_apply`, `kubectl_patch`, `kubectl_scale`, `kubectl_rollout` e
`install_helm_chart`** (`acesso/prova-tools-list.txt`). "Não destrutivo" não é
"só leitura". Daí as três camadas extras.

### 2. Triagem sem método (a linha de base)

Os três chamados foram triados em sessões limpas (`claude -p`), **sem nenhuma
skill** (`--disable-slash-commands`), só com o MCP. O pedido foi o texto do
chamado e nada mais (`execucoes/prompts.sh`). Resultado em
`execucoes/sem-skill/`.

O modelo achou a causa nos três. Mas cada sessão começou por um lugar
diferente e cometeu erros de método:

| Chamado | Ordem que a sessão seguiu | O que virou regra na skill |
|---|---|---|
| 1 | pods → LimitRange → Quota → describe → logs → deployment | tabela "sintoma → camada de entrada"; "OOMKilled no start não deixa log" (armadilha) |
| 2 | pods → deploy → events → RS → describe | trilha Workload: deploy → condições/RS → pods → eventos |
| 3 | `get all` → Ingress → **Endpoints** (descontinuado) → service → pods → **Ingress em todos os namespaces** | usar EndpointSlice e ler `conditions.ready`; não sair do namespace sem motivo dado pelo cluster |
| 3 | afirmou "o proxy de borda responde 503" sem ter visto proxy nenhum | armadilha "503 vem de quem está na frente: não afirme quem" |
| todos | emendaram achados paralelos no meio da causa | achados paralelos numa linha no fim, sem investigação |
| 1 e 2 | contrastaram o relato com o cluster ("o corte não foi no namespace", "não houve substituição") | virou campo fixo do formato: "O relato bate com o cluster?" |
| 1 e 2 | usaram o vizinho saudável (Postgres) como argumento | virou critério de parada: **contraprova** |

O que a linha de base fez bem entrou como passo do método. O que fez mal
entrou como regra ou armadilha.

### 3. Empacotamento

O método foi escrito em `skill/triagem-de-cluster/SKILL.md`: escopo,
entrada, ordem, cruzamento, parada e formato. As armadilhas foram para
`references/armadilhas.md`, lido sob demanda. A skill foi instalada como skill
de projeto (`.claude/skills/triagem-de-cluster`).

### 4. Execução e iteração

- **v1** rodou nos três chamados (`execucoes/com-skill/`). Disparou sozinha nos
  três, sem ser citada.
- A **matriz de roteamento** (rodada 1) achou o defeito que gerou a **v2**:
  - com "por que esse deployment está 0/3", sem namespace, a sessão fez grep
    no repositório, abriu `lab-dev` e percorreu **todos** os namespaces do
    cluster, inclusive um que não é do desafio;
  - com "o Service do nyx", triou os dois ambientes do cliente em 19 turnos.

  Num provedor multi-cliente, ler namespace de outro cliente é problema de
  isolamento, não só de custo. A v2 ganhou a seção **"0. Escopo"**: sem
  namespace, pergunta e para.
- A rodada 2 da matriz confirmou a correção, e a segunda repetição dos três
  chamados (`*.r2.*`) rodou com a v2.
