# PRD: `roster-audit`, auditoria de VM por SSH

| | |
|---|---|
| Status | aprovado para a v1 |
| Origem | [brainstorm](00-brainstorm.md) |
| Decisões técnicas | [TRD](02-TRD.md), [ADRs](adr/) |

## 1. Problema

O Roster, inventário do parque, é mantido à mão e está desatualizado. Há
hosts que mudaram de papel, agentes instalados e nunca registrados, chaves SSH
que ficaram para trás. Ninguém consegue dizer quantas VMs estão fora do padrão,
porque não existe coleta reproduzível do estado real de uma VM.

## 2. Objetivo

Ser a primeira peça do substituto do Roster: uma ferramenta de linha de
comando que audita **uma** VM por SSH, compara com o `baseline.yaml` e devolve
o resultado em JSON (para o Roster) e Markdown (para o plantão).

## 3. Usuários e usos

| Usuário | Uso | Formato |
|---|---|---|
| Plantonista | auditar o host do chamado | Markdown no terminal |
| Pipeline do Roster | auditar o parque em lote, um host por execução | JSON + código de saída |
| Segurança | saber o que está fora do padrão **e** o que não pôde ser verificado | qualquer um dos dois |

## 4. Requisitos funcionais

| ID | Requisito |
|---|---|
| RF-01 | Recebe endereço, porta (padrão 22), usuário e caminho da chave privada |
| RF-02 | Conecta por SSH e coleta, numa execução: identificação (endereço usado, hostname reportado, instante UTC), SO (distribuição e versão), kernel, unidades ativas (distinguindo `service` de `socket`), swap (habilitado e tamanho), portas TCP em escuta (porta, bind, processo), chaves SSH autorizadas (quantidade e identificação), login de root efetivo no `sshd`, sincronização de tempo (estado e mecanismo) |
| RF-03 | Compara com o baseline e produz **uma entrada por regra** com: regra, esperado, encontrado, veredito |
| RF-04 | Veredito ∈ {`conforme`, `desvio`, `nao_verificado`}. `desvio` traz a severidade do baseline; `nao_verificado` traz o motivo |
| RF-05 | Dado que exige privilégio e não pôde ser lido vira `nao_verificado` na regra correspondente. A execução continua |
| RF-06 | Saída em JSON, no formato do enunciado, e em Markdown, no formato do enunciado. Os dois saem do mesmo dado |
| RF-07 | Host inalcançável (endereço errado, porta fechada, chave recusada, host key divergente, timeout) falha com mensagem que explica o que houve, sem stack trace, com código de saída próprio |
| RF-08 | `--sudo` opcional: tenta `sudo -n` só para os dados que exigem privilégio; nunca pede senha |
| RF-09 | O baseline é um arquivo (`--baseline`), com um padrão embutido igual ao do enunciado |

## 5. Requisitos não funcionais

| ID | Requisito |
|---|---|
| RNF-01 | **Só leitura.** Nada é instalado, escrito ou alterado no host auditado. O único efeito colateral é o registro do próprio login SSH (`wtmp`, `auth.log`), inerente a qualquer acesso |
| RNF-02 | **Determinismo.** Duas execuções seguidas devolvem o mesmo veredito em todas as regras. Só `coletado_em` muda |
| RNF-03 | **A chave privada é credencial.** Nem o conteúdo nem o caminho da chave aparecem na saída, no log ou em mensagem de erro |
| RNF-04 | Código de saída utilizável em pipeline (tabela no TRD) |
| RNF-05 | Roda na estação do operador sem dependência além de Python 3.10+, PyYAML e o cliente OpenSSH |
| RNF-06 | Uma auditoria leva menos de 15 s num host saudável na mesma rede |

## 6. Critérios de pronto (aceite)

Vêm do enunciado. Cada um tem evidência em [`evidencias/`](../evidencias/).

| ID | Critério |
|---|---|
| CA-1 | Um host conforme sai **sem nenhum desvio** |
| CA-2 | Um host com desvios sai com **cada desvio classificado** pela severidade do baseline |
| CA-3 | Regra não verificável aparece como `nao_verificado`, **separada** de `conforme` |
| CA-4 | Host inalcançável falha com mensagem explicativa, sem stack trace, e **não** é confundido com host conforme (código de saída diferente de 0) |
| CA-5 | A segunda execução devolve o mesmo resultado |

## 7. Fora do escopo da v1

- Vários hosts numa execução; publicar no Roster; corrigir o host.
- Firewall e security group (o veredito de porta é pelo endereço de bind).
- Portas UDP.
- Assinatura de chave por CA SSH.
- Distribuições não Ubuntu (viram desvio, não erro).

## 8. Métrica de sucesso

Rodar no parque inteiro e o Roster passar a ter, para cada VM, a última
auditoria com data. A pergunta "quantas VMs estão fora do padrão" passa a ser
respondida por contagem, não por opinião.
