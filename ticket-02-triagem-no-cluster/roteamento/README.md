# Matriz de roteamento entre as duas skills

## Como foi medido

- Uma sessão **limpa** por frase: `claude -p`, sem histórico e sem sessão
  salva. As duas skills estavam instaladas como skills de projeto. O agente
  escolhe só pela `description` de cada uma.
- Mesmo ambiente das triagens: MCP só de leitura. `Bash`, `Write` e `Edit` foram
  bloqueados para a frase não agir de verdade, porque o objetivo é medir rota.
- Script: [`roda-matriz.sh`](roda-matriz.sh). Sessões brutas em `rodada-N/NN.jsonl`.
- "Skill disparada" = a primeira chamada à ferramenta `Skill`, ou "nenhuma".

## Rodada 1 (skills v1)

| # | Frase | Esperado | Disparou | Avaliação |
|---|---|---|---|---|
| 01 | o pod do nyx-prod não sobe | triagem | triagem | ✔ |
| 02 | por que esse deployment está 0/3 | **ambígua**: triagem, mas sem namespace | triagem | ⚠ rota certa, **conduta errada**: grep no repo, `lab-dev`, varreu todos os namespaces (15 turnos, US$ 0,24) |
| 03 | o service do nyx-stg não tem endpoint | triagem | triagem | ✔ |
| 04 | revisa esse deployment antes de eu subir | padrão | padrão | ✔ perguntou qual arquivo |
| 05 | esse manifesto está no padrão da casa? | padrão | padrão | ✔ perguntou qual arquivo |
| 06 | cria um Deployment novo do zero pra mim | padrão (escrita) | padrão | ✔ perguntou projeto, imagem, ambiente |
| 07 | esse manifesto não sobe no cluster | **ambígua**: padrão (o apply falha) ou triagem (subiu e não fica de pé) | nenhuma | ✔ **pergunta de desambiguação**: "o apply falha → confiro o YAML; o apply passa e o pod não fica de pé → triagem" |
| 08 | o Service do nyx não está entregando tráfego | **ambígua**: triagem, mas sem ambiente | triagem | ⚠ rota certa, **conduta errada**: triou `nyx-prod` e `nyx-stg` (19 turnos, US$ 0,31) |
| 09 | o que é um DaemonSet? | fora do escopo (conceito) | nenhuma | ✔ respondeu direto |
| 10 | provisiona uma VM nova no Construct pro cliente orion | fora do escopo (nenhuma skill, sem ferramenta) | nenhuma | ✔ disse que não tem acesso ao Construct e pediu como acessar |

**Nenhum disparo errado entre as duas skills.** As descrições separam
"antes de subir" (padrão) de "já rodando e quebrou" (triagem), e cada uma
tem um "NÃO use para…" apontando para a outra. Os dois problemas foram de
**conduta depois do disparo certo**, em frases sem namespace.

## O que mudou por causa da rodada 1

| Caso | Decisão | Onde |
|---|---|---|
| 02 e 08 | **Mudar a skill**. Num cluster multi-cliente, a triagem não pode sair procurando: sem namespace, pergunta e para; com cliente e sem ambiente, pergunta qual | seção "0. Escopo" do `SKILL.md` da triagem |
| 02 e 08 | **A frase também estava mal formulada.** O plantonista precisa dizer o namespace. Reescrita e testada na rodada 3 | abaixo |
| 07 | **Não mudar nada.** Não disparar e perguntar é o comportamento certo para uma frase que serve às duas skills. Forçar uma das descrições a capturá-la erraria metade dos casos | — |
| 09 | **Não mudar nada.** O Bloco 4 do padrão (vocabulário) foi cortado da skill de manifests de propósito (curadoria do Ticket 01). Se ele estivesse lá, esta frase poderia disparar a skill à toa | — |
| 10 | **Não mudar nada.** Fora do escopo das duas, e o agente não fingiu provisionar | — |

## Rodada 2 (triagem v2)

| # | Frase | Disparou | Turnos | Custo US$ | Comportamento |
|---|---|---|---|---|---|
| 01 | o pod do nyx-prod não sobe | triagem | 11 | 0,157 | triou `nyx-prod` |
| 02 | por que esse deployment está 0/3 | triagem | **3** | **0,035** | "Não sei qual namespace nem qual deployment… não vou listar namespaces nem procurar pelo cluster" |
| 03 | o service do nyx-stg não tem endpoint | triagem | 10 | 0,178 | triou `nyx-stg` |
| 04 | revisa esse deployment antes de eu subir | padrão | 4 | 0,071 | pediu o arquivo |
| 05 | esse manifesto está no padrão da casa? | padrão | 4 | 0,070 | pediu o arquivo |
| 06 | cria um Deployment novo do zero pra mim | padrão | 3 | 0,043 | pediu projeto e imagem |
| 07 | esse manifesto não sobe no cluster | nenhuma | 2 | 0,045 | mesma pergunta de desambiguação |
| 08 | o Service do nyx não está entregando tráfego | triagem | **3** | **0,035** | "Qual deles é: `nyx-dev`, `nyx-stg` ou `nyx-prod`?" |
| 09 | o que é um DaemonSet? | nenhuma | 1 | 0,023 | resposta direta |
| 10 | provisiona uma VM nova no Construct pro cliente orion | nenhuma | 3 | 0,073 | sem acesso ao Construct |

A rota das 10 frases não mudou entre as rodadas. Só a conduta de 02 e 08.
O custo menor na rodada 2 se deve em parte ao cache de prompt, que já estava
aquecido.

## Rodada 3: as frases ambíguas reformuladas

| Frase reformulada | Disparou | Turnos | Resultado |
|---|---|---|---|
| por que o deployment `orion-web` do `orion-stg` está 0/3 | triagem | 9 | causa: tag `v1.14.2` inexistente |
| o Service `nyx-api` do `nyx-stg` não está entregando tráfego | triagem | 12 | causa: seletor `nyx-api` × rótulo `nyxapi` |

Com o namespace na frase, a mesma skill vai direto à causa. **Correção de
processo**, além da skill: o template de abertura de chamado do plantão deve
pedir namespace e objeto.
