## 1. Estrutura

- [x] 1.1 Criar `src/retrato/` (`__main__`, `leitura`, `retrato`, `servidor`, `static/index.html`) e `requirements.txt` com `kubernetes==37.0.1`; verificar com `python3 -m retrato --help`

## 2. Leitura da API

- [x] 2.1 Implementar `leitura.py`: carga do kubeconfig na subida (contexto corrente), `lista_*` com timeout `(3, 8)`, classificação de falhas (TRD §3); verificar com testes de classificação para conexão recusada, 401, 403 e 404
- [x] 2.2 Escrever o teste de AST de só leitura e verificar que ele falha ao inserir um `create_namespace` de propósito

## 3. Regras de exibição

- [x] 3.1 Implementar `retrato.py` (pods, deployments, services com EndpointSlice, eventos) e verificar com testes de campos ausentes (`readyReplicas`, `endpoints`, `containerStatuses`)
- [x] 3.2 Montar o retrato com as cinco listagens em paralelo e seções independentes; verificar com teste em que uma listagem falha e as outras seguem

## 4. Servidor e tela

- [x] 4.1 Implementar `servidor.py` (só GET em 127.0.0.1, 405 no resto) e verificar com teste HTTP
- [x] 4.2 Implementar `index.html` (seletor, busca, quatro seções, faixa de erro, intervalo, pausa com aba oculta, `textContent`); verificar abrindo contra o kind

## 5. RBAC de exemplo

- [x] 5.1 Escrever `deploy/rbac-retrato-leitura.yaml` e `deploy/gera-kubeconfig.sh`; verificar com `kubectl auth can-i`

## 6. Validação

- [x] 6.1 CA-1: capturar a tela de `nyx-prod`, `orion-stg` e `nyx-stg` com os defeitos visíveis e dos workloads do Ticket 01 (`orion-prod`, `nyx-dev`)
- [x] 6.2 CA-2: capturar a tela com cluster inacessível, com token expirado e com papel restrito (sem events e endpointslices)
- [x] 6.3 CA-3: rodar a suíte com o teste de só leitura e registrar a saída
