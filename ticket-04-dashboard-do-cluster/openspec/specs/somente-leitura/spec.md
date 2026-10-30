# somente-leitura Specification

## Purpose
Tornar verificável, e não só intencional, que a aplicação nunca escreve no
cluster.

## Requirements

### Requirement: Nenhuma chamada de escrita no código
O código MUST NOT conter chamadas à API do Kubernetes que não sejam de leitura (`list_*`, `read_*`), e somente um módulo SHALL importar o cliente do Kubernetes.

#### Scenario: Verificação automática
- **WHEN** a suíte de testes roda
- **THEN** um teste analisa o código-fonte e falha se encontrar `create_`, `patch_`, `replace_`, `delete_`, `connect_`, `call_api` ou um segundo módulo importando `kubernetes`

### Requirement: Servidor só aceita leitura
O servidor HTTP SHALL atender apenas GET e SHALL responder 405 a POST, PUT, PATCH e DELETE, e SHALL escutar apenas em `127.0.0.1`.

#### Scenario: Método de escrita
- **WHEN** alguém envia `POST /api/retrato/nyx-prod`
- **THEN** a resposta é 405 e nada é chamado na API do Kubernetes

### Requirement: Papel de leitura de exemplo
O projeto SHALL fornecer uma ClusterRole com apenas `get`, `list` e `watch` nos recursos exibidos, e um script que gera um kubeconfig com ela.

#### Scenario: Escrita negada pelo cluster
- **WHEN** a aplicação roda com o kubeconfig gerado a partir da ClusterRole de exemplo
- **THEN** `kubectl auth can-i` com esse kubeconfig responde `no` para create, patch e delete
