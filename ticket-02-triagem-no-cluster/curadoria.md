# Curadoria da skill `triagem-de-cluster`

## 1. O que o método fixou e o que ficou a critério do agente

| Fixado pelo método | Por quê |
|---|---|
| **Escopo: um namespace, dito pelo usuário.** Sem namespace, pergunta e para | o cluster é multi-cliente; na matriz, sem essa regra, a sessão percorreu todos os namespaces |
| **Camada de entrada pelo sintoma** (reinício → Pod; não sobe/não atualiza → Workload; 503/sem endpoint → Tráfego) | a linha de base começou por um lugar diferente a cada sessão |
| **Ordem de descida** dentro de cada trilha | cada camada só é aberta quando a anterior está explicada |
| **Quando cruzar fontes:** tabela de "sinal genérico → fonte a cruzar" (137 → limits; `BackOff` → mensagem do kubelet × imagem; EndpointSlice vazio → seletor × rótulos) | aprofundar na mesma fonte não resolve sinal genérico |
| **Critério de parada:** mecanismo observado + atributo que explica + contraprova | evita abrir a próxima camada "por garantia" e evita parar no sintoma |
| **EndpointSlice no lugar de Endpoints**, lendo `conditions.ready` | Endpoints está descontinuado; no `nyx-prod`, o slice mostra IPs com 0/2 pods prontos |
| **Formato da entrega** (Causa, Camada, Evidências com fonte, Contraprova, Relato × cluster, Correção não aplicada, Não verificado) | o plantonista seguinte lê sem refazer a triagem |
| **Limite absoluto: só leitura**, mesmo com permissão | pedido da SRE; garantido também fora do texto (§2) |

| A critério do agente | Por quê |
|---|---|
| Quais objetos descrever dentro da camada (qual pod, qual evento) | depende do que o cluster mostra |
| Quantas chamadas fazer até ter as três provas | um chamado simples fecha em 4; um ambíguo precisa de mais |
| Ler `armadilhas.md` ou não | é referência; as seis execuções com skill leram |
| A correção sugerida (valores, onde mexer) | é texto para um humano decidir |
| Achados paralelos | podem ser citados, numa linha, sem investigação |

O que **não** foi fixado de propósito: lista de comandos por chamado. A skill
descreve camadas e critérios, não um roteiro dos três chamados do laboratório.
Um roteiro teria acertado os três e falhado no quarto.

## 2. Como garanti que a skill não escreve no cluster

Quatro camadas independentes. Cada uma, sozinha, bloqueia a escrita. A
primeira é a única que o enunciado pede, e ela **não basta**.

| # | Camada | O que bloqueia | Evidência |
|---|---|---|---|
| 1 | `ALLOW_ONLY_NON_DESTRUCTIVE_TOOLS=true` (enunciado) | só `delete`, `exec`, `generic`, `node_management`, `cleanup`, `uninstall`. **Ainda expõe `kubectl_apply`, `kubectl_create`, `kubectl_patch`, `kubectl_scale`, `kubectl_rollout`, `install_helm_chart`, `upgrade_helm_chart`, `port_forward`** | [`acesso/prova-tools-list.txt`](acesso/prova-tools-list.txt), segunda linha |
| 2 | `ALLOWED_TOOLS=kubectl_get,kubectl_describe,kubectl_logs,explain_resource,list_api_resources,ping` no servidor (prevalece sobre os outros modos, `src/index.ts`) | o servidor só **expõe** essas 6 ferramentas | [`acesso/prova-tools-list.txt`](acesso/prova-tools-list.txt), primeira linha |
| 3 | `KUBECONFIG` próprio, com a ServiceAccount `triagem-leitura` ligada ao ClusterRole `view` | o **apiserver** recusa qualquer escrita, inclusive se as camadas 1 e 2 falharem ou se alguém usar `kubectl` pelo shell com esse kubeconfig. `view` também não lê Secrets | [`acesso/rbac-triagem-leitura.yaml`](acesso/rbac-triagem-leitura.yaml), [`acesso/prova-auth-can-i.txt`](acesso/prova-auth-can-i.txt) |
| 4 | `.claude/settings.json` do projeto: `deny` para as 18 ferramentas de escrita do servidor; `allowed-tools` da skill só com as 6 de leitura | o **Claude Code** recusa a chamada antes de ela sair | [`.claude/settings.json`](../.claude/settings.json) |

Mais duas medidas:

- **Texto da skill:** o "Limite absoluto" manda registrar como "não
  verificado: exigiria <ação>" o que só se confirmaria com escrita. No
  chamado 3, nas duas repetições, "testar a chamada de fora" apareceu assim,
  como "não verificado", porque exigiria port-forward ou exec.
- **Execuções sem shell:** as sessões de comparação rodaram com `Bash`,
  `Write` e `Edit` em `--disallowedTools`. A proteção também está na
  configuração do MCP, no `ALLOWED_TOOLS` e no `deny` do Claude Code.

O servidor está fixado na versão **4.1.9** (de 2026-10-02). A 4.2.1 tinha sido
publicada no mesmo dia do trabalho. Fixar uma versão de semanas atrás reduz
o risco de puxar um pacote comprometido recém-publicado num servidor com
acesso ao cluster.

## 3. O que ficou no corpo e o que virou arquivo sob demanda

| Arquivo | Conteúdo | Quando é lido |
|---|---|---|
| `SKILL.md` (~6,5 KB) | limite, escopo, entrada, ordem, cruzamento, parada, formato | sempre que dispara |
| `references/armadilhas.md` (~2 KB) | nove armadilhas vistas no parque (CrashLoop com fase Running, OOM sem log, EndpointSlice com IP não pronto, campo ausente, recusa no ReplicaSet, três causas de ImagePull, "não foi substituído", "limite no namespace", 503 de quem está na frente) | quando a trilha empaca; na prática, todas as execuções leram |

Como todas as execuções leram `armadilhas.md`, mantê-lo separado não economizou
contexto nos três chamados. Mantive assim porque ele é a parte que cresce
com o tempo, a cada incidente novo. O corpo deve ficar estável.

## 4. Saídas ruins e o que eu faria diferente

- **Rodada 1 da matriz, frases 02 e 08:** varredura do cluster inteiro e
  triagem de dois ambientes. Corrigido na v2 (seção Escopo). Ver `roteamento/`.
- **Chamado 3 com skill, rep. 1:** 44,6 s e 8 chamadas, contra 4 nos outros.
  O agente confirmou o seletor três vezes (`get pods -l app=nyx-api`,
  `-l app=nyxapi`, `--show-labels`). A regra de parada estava satisfeita
  antes. Faria diferente: dizer no critério de parada que uma evidência
  conclusiva não precisa ser repetida por outro caminho.
- **A skill não melhora o acerto nestes chamados.** O modelo acerta sem ela
  (ver `comparacao-com-e-sem-skill.md`). O ganho é de método, escopo e formato,
  a um custo de +46%. Para medir o ganho de acerto, faltam chamados em que a
  causa cruza camadas.
