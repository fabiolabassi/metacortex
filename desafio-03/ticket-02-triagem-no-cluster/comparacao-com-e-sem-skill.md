# A skill vale o custo? Com × sem skill

## Como foi medido

- **Casos:** os três chamados, cada um em **duas repetições** por modo (12 sessões).
- **Mesmas condições nos dois modos:**
  - texto do pedido idêntico (`execucoes/prompts.sh`);
  - modelo `claude-opus-5-5`;
  - MCP só de leitura, com as mesmas ferramentas;
  - `Bash`/`Write`/`Edit` bloqueados;
  - três sessões em paralelo por modo.
- **Sem skill:** `--disable-slash-commands`, que desliga todas as skills.
- **Com skill:** a skill instalada, sem ser citada no pedido. A rep. 1 usou a
  v1, e a rep. 2 a v2. A diferença entre as duas (seção "Escopo") não altera
  pedido com namespace.
- **Números:** do evento `result` de cada sessão (`duration_ms`, `num_turns`,
  `usage`, `total_cost_usd`), extraídos por `ferramentas/resumo-sessao.py`.
- **"Fora do ns":** chamadas MCP fora do namespace do chamado.
- **"Formato":** quantas das 4 seções do método aparecem (Causa, Contraprova,
  Relato bate?, Não verificado).

## Números

| Modo | Chamado | Rep | Tempo (s) | Turnos | Chamadas MCP | Fora do ns | Tokens entrada | Tokens saída | Custo (US$) | Formato |
|---|---|---|---|---|---|---|---|---|---|---|
| sem | 1 | 1 | 26,4 | 8 | 6 | 0 | 53.649 | 2.129 | 0,140 | 0/4 |
| sem | 1 | 2 | 28,6 | 9 | 7 | 0 | 77.240 | 2.213 | 0,139 | 0/4 |
| sem | 2 | 1 | 25,4 | 7 | 5 | 0 | 58.538 | 2.140 | 0,146 | 0/4 |
| sem | 2 | 2 | 25,2 | 7 | 4 | 0 | 82.765 | 2.360 | 0,150 | 0/4 |
| sem | 3 | 1 | 22,4 | 8 | 6 | **1** | 55.359 | 2.044 | 0,146 | 0/4 |
| sem | 3 | 2 | 24,1 | 8 | 6 | **1** | 65.380 | 1.867 | 0,088 | 1/4 |
| com | 1 | 1 | 28,2 | 9 | 4 | 0 | 135.065 | 2.092 | 0,227 | 4/4 |
| com | 1 | 2 | 31,3 | 10 | 5 | 0 | 136.298 | 2.475 | 0,159 | 4/4 |
| com | 2 | 1 | 30,9 | 9 | 4 | 0 | 134.471 | 2.108 | 0,233 | 4/4 |
| com | 2 | 2 | 29,4 | 9 | 4 | 0 | 133.368 | 2.135 | 0,133 | 4/4 |
| com | 3 | 1 | 44,6 | 13 | 8 | 0 | 189.145 | 2.585 | 0,255 | 4/4 |
| com | 3 | 2 | 27,0 | 12 | 7 | 0 | 193.059 | 2.473 | 0,178 | 4/4 |

**Médias:**

| | Tempo | Turnos | MCP | Tokens entrada | Tokens saída | Custo |
|---|---|---|---|---|---|---|
| sem skill | 25,4 s | 7,8 | 5,7 | 65.489 | 2.126 | US$ 0,135 |
| com skill | 31,9 s | 10,3 | 5,3 | 153.567 | 2.311 | US$ 0,198 |
| diferença | **+26%** | +32% | −6% | **+134%** | +9% | **+46%** |

## Qualidade da saída

**As 12 sessões acharam a causa certa.** O modelo, sozinho e com acesso ao
cluster, resolve estes três chamados. A skill não melhora o acerto. O que
muda é o seguinte:

| Aspecto | Sem skill | Com skill |
|---|---|---|
| Por onde começa | varia por sessão: pods, `get all`, deployments | fixo pela tabela sintoma → camada (pods / deployments / services) |
| Fonte de endpoint | `Endpoints`, descontinuado (chamado 3, nas duas reps.) | `EndpointSlice`, lendo `conditions.ready` |
| Fora do namespace | listou **Ingress de todos os namespaces** no chamado 3, nas duas reps. | nenhuma chamada fora do namespace |
| Afirmação sem evidência | "o proxy de borda responde 503" (chamado 3, rep. 1) | "Não verificado: quem devolve o 503. Não olhei Ingress nem Gateway" |
| Contraprova (vizinho saudável) | aparece às vezes, solta no texto | sempre, em campo próprio |
| Relato × cluster | aparece em 1 e 2, como digressão | sempre, em campo próprio ("Em parte. O cluster não mostra limite no namespace inteiro") |
| O que não foi verificado | raramente dito | sempre, em campo próprio |
| Achados paralelos | misturados com a causa (senha em texto, probe faltando) | numa linha no fim |
| Formato | diferente a cada sessão | idêntico nas 6 |

## Leitura

- **Custo:** +46% em dinheiro e +134% em tokens de entrada. Os tokens de
  entrada contam o contexto **relido a cada turno**, e por isso crescem por
  dois motivos que se somam. O `SKILL.md` e o `armadilhas.md` (~8,5 KB, cerca
  de 2,4 mil tokens) ficam no contexto de todos os turnos depois do disparo. E
  há ~2,5 turnos a mais por sessão (a chamada `Skill` e a leitura das
  armadilhas, mais as consultas de confirmação), cada um relendo um contexto
  que já tem as saídas YAML do cluster. A maior parte é leitura de cache
  (barata), por isso o custo sobe bem menos que os tokens. Os tokens de saída
  quase não mudam (+9%): a skill não faz o modelo escrever mais, faz ele ler mais.
- **Tempo:** +6,5 s em média. Um outlier (chamado 3, rep. 1: 44,6 s) puxa a
  média; sem ele, a diferença é de ~4 s.
- **Chamadas ao cluster:** praticamente iguais (5,3 × 5,7). A skill não
  economiza leitura nestes casos fáceis, mas lê **onde deve** (dentro do
  namespace, EndpointSlice no lugar de Endpoints).

**Vale o custo?** Para estes três chamados, medidos por acerto da causa,
**não**: o modelo acerta sem a skill, e mais barato. A skill se paga em três
outras frentes:

1. **Previsibilidade do plantão.** A saída tem sempre o mesmo formato, com
   evidência, contraprova e o que ficou de fora. Isso é o "método único" que
   a SRE pediu. É o que permite passar o chamado para outra pessoa sem reler
   o cluster.
2. **Isolamento entre clientes.** Sem skill, o agente consultou outros
   namespaces nas duas repetições do chamado 3. Na matriz de roteamento, sem
   a seção "Escopo", a sessão percorreu o cluster inteiro. Num provedor
   gerenciado, isso não é detalhe de custo.
3. **O caso ambíguo fica barato.** Sem namespace, a triagem v2 para em 3
   turnos e US$ 0,035, contra 15 a 19 turnos e até US$ 0,31 na v1.

**O que eu faria diferente:** medir com chamados difíceis, em que a causa
cruza camadas (ex.: Pod Security recusando o pod, com o motivo só nos eventos
do ReplicaSet). É ali que a ordem de descida e a regra de cruzamento devem
mudar o acerto, não só o formato. Também mediria com um modelo menor
(Sonnet/Haiku), em que o método escrito tende a pesar mais.
