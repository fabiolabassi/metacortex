# PRD: `retrato`, dashboard de leitura do cluster

| | |
|---|---|
| Status | aprovado para a primeira fatia |
| Origem | [brainstorm](00-brainstorm.md) |
| Decisões | [TRD](02-TRD.md), [ADRs](adr/) |

## 1. Problema

O plantonista gasta os primeiros minutos de cada chamado montando, comando a
comando, o retrato de um namespace. A informação existe na API. O que falta é
vê-la junta.

## 2. Objetivo

Aplicação local que mostra o retrato de um namespace, usando o kubeconfig e o
contexto corrente de quem a roda. Não substitui o terminal.

## 3. Requisitos funcionais

| ID | Requisito |
|---|---|
| RF-01 | Lê o **contexto corrente** do kubeconfig **na subida** e mostra contexto, cluster e usuário. Não há seletor de cluster nem troca de contexto |
| RF-02 | Lista os **namespaces** do cluster |
| RF-03 | Para o namespace selecionado, mostra **pods** com estado, prontos/total de containers, contagem de **reinícios** e **motivo** quando em falha (`CrashLoopBackOff`, `OOMKilled`, `ImagePullBackOff`, `Unschedulable`...) |
| RF-04 | Mostra **deployments** com réplicas **prontas/desejadas** |
| RF-05 | Mostra **services** e se têm **endpoint pronto** (nenhum, N prontos, porta não resolvida) |
| RF-06 | Mostra **eventos recentes** do namespace selecionado (Warning primeiro), com objeto, motivo, mensagem, contagem e quando |
| RF-07 | **Filtro por namespace** e **busca por nome** (pods, deployments, services e objeto dos eventos) |
| RF-08 | Atualiza sozinho em intervalo fixo, com botão "atualizar agora" e pausa quando a aba não está visível |
| RF-09 | Indica quando "pronto" não diz nada sobre saúde (container sem readinessProbe) |

## 4. Comportamento quando o ambiente falha

| ID | Situação | Comportamento |
|---|---|---|
| RF-10 | Contexto aponta para cluster que não responde | a página abre; faixa "o cluster X não respondeu em N s"; continua tentando |
| RF-11 | Credencial expirada ou inválida (401) | faixa "credencial recusada pelo cluster (expirada ou inválida)", com a dica de renovar o login |
| RF-12 | Permissão negada para um tipo de recurso (403) | só a seção afetada mostra "sem permissão para listar <recurso>"; as demais funcionam. Sem permissão de listar namespaces: usa o namespace do contexto e aceita digitar |

Em nenhum caso aparece tela em branco ou stack trace, nem no navegador nem no console.

## 5. Requisitos não funcionais

| ID | Requisito |
|---|---|
| RNF-01 | **Só leitura**, visível no código (um módulo só, com verbos de leitura e um teste que o garante), no servidor HTTP (só GET) e numa ClusterRole de exemplo |
| RNF-02 | Escuta só em `127.0.0.1` |
| RNF-03 | Carga sobre o apiserver: no máximo 5 listagens por intervalo, só do namespace selecionado |
| RNF-04 | Python 3.10+ e uma dependência (cliente oficial do Kubernetes); sem build de frontend |
| RNF-05 | Campo ausente na API é tratado como zero/vazio, nunca como erro |

## 6. Critérios de aceite

| ID | Critério |
|---|---|
| CA-1 | Contra o kind com os workloads do Ticket 01 e os chamados do Ticket 02, a tela mostra os três defeitos: OOMKilled no `nyx-prod`, ImagePullBackOff no `orion-stg`, Service sem endpoint no `nyx-stg` |
| CA-2 | Os três cenários de falha da seção 4 são exibidos como descrito, com evidência |
| CA-3 | Não existe caminho no código que faça escrita na API (teste) |
