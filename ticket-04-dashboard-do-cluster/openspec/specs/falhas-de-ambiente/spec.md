# falhas-de-ambiente Specification

## Purpose
Garantir que a aplicação continue útil e legível quando o ambiente falha, sem
tela em branco e sem stack trace.

## Requirements

### Requirement: Cluster que não responde
Quando o servidor do contexto corrente não responde dentro do timeout, a aplicação SHALL abrir normalmente e SHALL exibir uma faixa dizendo qual servidor não respondeu, continuando a tentar a cada intervalo.

#### Scenario: Servidor inacessível
- **WHEN** o kubeconfig aponta para `https://127.0.0.1:1`
- **THEN** a página carrega, mostra a faixa de cluster inacessível em até ~3 s e nenhum traceback aparece no console

### Requirement: Credencial expirada
Quando o apiserver recusa a credencial (401), a aplicação SHALL exibir uma faixa dizendo que a credencial foi recusada (expirada ou inválida) e o que fazer.

#### Scenario: Token expirado
- **WHEN** o kubeconfig usa um token de ServiceAccount já expirado
- **THEN** a faixa diz que a credencial do contexto foi recusada e sugere renovar o login

### Requirement: Permissão negada por recurso
Quando o apiserver nega (403) a listagem de um tipo de recurso, a aplicação SHALL mostrar a negação apenas na seção afetada, e as demais seções SHALL continuar exibindo seus dados.

#### Scenario: Leitura restrita sem eventos
- **WHEN** o usuário do contexto pode listar pods, deployments e services, mas não events nem endpointslices
- **THEN** as seções de pods, deployments e services mostram dados; a de eventos mostra "sem permissão para listar events"; a coluna de endpoint mostra "sem permissão"

#### Scenario: Sem permissão de listar namespaces
- **WHEN** o usuário não pode listar namespaces
- **THEN** o seletor usa o namespace do contexto e aceita digitar outro, com aviso

### Requirement: Sem traceback
Nenhum erro de ambiente SHALL produzir stack trace no console ou na página; erros inesperados SHALL virar mensagem genérica, com o detalhe disponível só com `--debug`.

#### Scenario: Erro inesperado
- **WHEN** a montagem de uma seção lança uma exceção não prevista
- **THEN** a seção mostra "erro interno ao montar a seção" e o console registra uma linha sem traceback
