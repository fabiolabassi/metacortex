# Armadilhas de triagem já vistas no parque

Consulte quando a trilha empacar ou quando a evidência parecer contraditória.

- **Pod em CrashLoopBackOff tem fase `Running`.** O estado de falha está em
  `containerStatuses[].state.waiting.reason` e em `lastState.terminated`, não
  em `status.phase`.
- **OOMKilled no start não deixa log.** Processo morto pelo kernel em menos de
  1s: `logs --previous` volta vazio. A evidência é `exitCode: 137` + `reason:
  OOMKilled` + `Started`/`Finished` quase iguais no describe.
- **EndpointSlice com IPs não é Service saudável.** Pods não prontos aparecem
  com `conditions.ready: false`. `targetPort` errado aparece com IPs e porta
  `<unset>`. Leia as condições, não só os endereços.
- **Campo ausente não é campo vazio.** `Endpoints` sem pod não traz `subsets`;
  Deployment sem réplica pronta não traz `readyReplicas`. Ausência = zero.
- **Deployment parado em 0/N sem pod nenhum**: o Pod foi recusado na
  admissão (Pod Security, ResourceQuota). O motivo está nos eventos do
  ReplicaSet (`FailedCreate`), não no Deployment.
- **`ImagePullBackOff` tem três causas com mensagens diferentes**: `not found`
  (tag ou repositório não existe), `unauthorized`/`denied` (credencial,
  `imagePullSecrets`) e timeout/`i/o` (rede, registry fora). Leia a mensagem.
- **"O pod nunca foi substituído"**: num rollout normal, com `maxUnavailable`
  baixo, os pods antigos ficam servindo e os novos travam. Se não há
  `OldReplicaSets` e a revisão é 1, o deploy foi criação do zero, sem versão
  anterior para voltar.
- **"Limites mudaram no namespace inteiro"** pode ser LimitRange/ResourceQuota
  **ou** o mesmo valor colado em cada Deployment. Verifique os dois antes de
  dizer onde corrigir. Um `kubectl rollout undo` não desfaz LimitRange.
- **503 vem de quem está na frente.** Se não há Ingress/Gateway no namespace,
  não afirme quem devolve o 503. Diga que endpoint vazio produz esse sintoma
  em qualquer proxy na frente do Service.
