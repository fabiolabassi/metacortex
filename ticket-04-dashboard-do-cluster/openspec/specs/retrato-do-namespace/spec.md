# retrato-do-namespace Specification

## Purpose
Mostrar numa tela o retrato de um namespace do cluster do contexto corrente,
com a mesma informação que a primeira rodada de comandos de uma triagem traria.

## Requirements

### Requirement: Contexto corrente fixo
A aplicação SHALL ler o contexto corrente do kubeconfig uma única vez, na subida, e SHALL exibir o nome do contexto, do cluster e do usuário. A aplicação MUST NOT oferecer seleção de cluster ou troca de contexto.

#### Scenario: Contexto exibido
- **WHEN** a aplicação sobe com o contexto corrente `kind-kind`
- **THEN** o cabeçalho mostra `kind-kind`, o servidor do cluster e o usuário, sem nenhum controle para trocá-los

### Requirement: Namespaces e filtro
A aplicação SHALL listar os namespaces do cluster num seletor, e todas as seções SHALL mostrar apenas o namespace selecionado.

#### Scenario: Troca de namespace
- **WHEN** o usuário seleciona `nyx-stg`
- **THEN** pods, deployments, services e eventos passam a ser os de `nyx-stg`

### Requirement: Pods com motivo de falha
Para cada pod, a aplicação SHALL mostrar nome, estado, containers prontos/total, total de reinícios e o motivo quando em falha, incluindo o motivo do último término do container.

#### Scenario: CrashLoop por falta de memória
- **WHEN** um pod tem container em `waiting.reason=CrashLoopBackOff` e `lastState.terminated.reason=OOMKilled` com `exitCode 137`
- **THEN** a linha mostra estado `CrashLoopBackOff`, último término `OOMKilled (137)` e a contagem de reinícios

#### Scenario: Pod pendente sem status de container
- **WHEN** um pod `Pending` ainda não tem `containerStatuses`
- **THEN** a linha mostra `0/N` prontos e `0` reinícios, sem erro

### Requirement: Deployments com prontas sobre desejadas
Para cada deployment, a aplicação SHALL mostrar réplicas prontas sobre desejadas, tratando `readyReplicas` ausente como 0.

#### Scenario: Nenhuma réplica pronta
- **WHEN** a API devolve um Deployment com `spec.replicas=3` e sem `status.readyReplicas`
- **THEN** a linha mostra `0/3` e o motivo da condição `Available=False`

### Requirement: Services com endpoint
Para cada Service, a aplicação SHALL indicar, a partir de EndpointSlices, se há endpoint pronto: sem endpoint, N de M prontos, ou porta não resolvida. Endereço com `conditions.ready` falso MUST NOT contar como pronto.

#### Scenario: Seletor que não casa
- **WHEN** o Service `nyx-api` tem slice com `endpoints` ausente
- **THEN** a linha mostra "sem endpoint" e a dica de que nenhum pod do namespace casa com o seletor

#### Scenario: IPs listados, nenhum pronto
- **WHEN** o slice do Service lista 2 endereços com `ready: false`
- **THEN** a linha mostra `0/2 prontos`, e não "com endpoint"

### Requirement: Eventos recentes
A aplicação SHALL mostrar os eventos do namespace selecionado, mais recentes primeiro, com tipo, motivo, objeto envolvido, mensagem, contagem e idade.

#### Scenario: Evento de BackOff
- **WHEN** existe um evento `Warning BackOff` para um pod do namespace
- **THEN** ele aparece com o objeto `Pod/<nome>`, a mensagem e a contagem

### Requirement: Busca por nome
A aplicação SHALL filtrar todas as seções por um texto digitado, comparando com o nome do objeto (e com o objeto envolvido, nos eventos).

#### Scenario: Busca
- **WHEN** o usuário digita `postgres` no namespace `nyx-prod`
- **THEN** só as linhas cujo nome contém `postgres` continuam visíveis

### Requirement: Limite de "pronto"
A aplicação SHALL marcar pods e deployments cujos containers não têm readinessProbe com a indicação de que "pronto" significa apenas que o processo está de pé.

#### Scenario: Sem readinessProbe
- **WHEN** um pod pronto não tem readinessProbe em nenhum container
- **THEN** a linha traz a marca "pronto = processo de pé"

### Requirement: Atualização periódica
A tela SHALL se atualizar sozinha em intervalo fixo (padrão 10 s), SHALL oferecer atualização manual e SHALL suspender a atualização enquanto a aba estiver oculta.

#### Scenario: Aba oculta
- **WHEN** a aba do navegador fica oculta
- **THEN** nenhuma requisição é feita ao servidor até ela voltar a ficar visível
