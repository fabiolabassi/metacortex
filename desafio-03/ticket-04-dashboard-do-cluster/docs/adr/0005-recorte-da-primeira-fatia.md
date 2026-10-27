# ADR-0005: Recorte da primeira fatia

- Status: aceito
- Data: 2026-10-27

## Contexto

O enunciado traz um mínimo de tela, três falhas de ambiente e uma restrição
de só leitura, e deixa "o que entra primeiro" em aberto. Toda funcionalidade
nova num dashboard com credencial de produção é superfície nova.

## Decisão

**Primeira fatia (esta spec):**

- contexto corrente na subida (sem troca);
- namespaces;
- pods (estado, prontos, reinícios, motivo);
- deployments (prontos/desejados);
- services (com ou sem endpoint, via EndpointSlice);
- eventos do namespace;
- filtro por namespace e busca por nome;
- atualização a cada 10 s;
- as três falhas de ambiente por seção;
- a marca "pronto ≠ saudável";
- a garantia de leitura em código, HTTP e RBAC.

**Depois:**

| Item | Por que fica para depois |
|---|---|
| Logs de container (`--previous`) | é o próximo passo natural da trilha Pod da triagem, mas exige `pods/log` e streaming, e muda o perfil de RBAC |
| Detalhe/YAML de um objeto | útil, mas é "describe na tela"; o terminal já faz bem |
| StatefulSet, DaemonSet, Job/CronJob | os workloads do laboratório são Deployments; o modelo de tabela já comporta |
| Ingress/Gateway | o 503 do chamado 3 vem de quem está na frente; entra quando o parque padronizar Gateway API |
| Métricas (CPU/memória) | depende de metrics-server; o OOMKilled já aparece como motivo |
| Nós | outro público (plataforma), outro RBAC |
| Watch / tempo real | ADR-0003 |

## Alternativas consideradas

| Alternativa | Ganha | Perde |
|---|---|---|
| **Mínimo + falhas + só leitura** (escolhida) | entrega o que encurta os primeiros minutos, com a robustez que um plantão exige; dá para auditar o "só leitura" inteiro | o plantonista ainda vai ao terminal para logs |
| **Mínimo + logs** | cobre a trilha Pod da triagem quase inteira sem sair da tela | streaming, `pods/log`, tamanho de resposta, mascarar segredo em log; dobra o escopo de teste |
| **Mínimo sem tratar falhas** (caminho feliz) | sai mais rápido | é exatamente o que o enunciado proíbe ("sem tela em branco nem stack trace"); dashboard que some quando o cluster está ruim não serve para triagem |

## Consequências

- (+) Spec pequena o suficiente para ser validada inteira contra o cluster real.
- (−) Logs ficam no terminal. É a primeira coisa da próxima fatia.
