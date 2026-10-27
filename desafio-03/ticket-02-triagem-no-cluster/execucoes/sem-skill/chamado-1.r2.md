## Causa: a API está sendo morta por falta de memória (OOMKilled)

O limite de memória do container `api` está em **24Mi**. O processo Node.js do kube-news passa desse valor logo na inicialização, e o kernel mata o container antes de ele ficar pronto.

**O que vi no cluster:**

- As duas réplicas de `nyx-api` estão em `CrashLoopBackOff`, com 7 restarts em 14 minutos.
- O `describe` do pod mostra `Last State: Terminated`, `Reason: OOMKilled`, `Exit Code: 137`.
- O container viveu só 5 segundos (de 20:47:43 a 20:47:48). Ele morre antes da primeira readiness probe, que espera 10s (`initialDelaySeconds: 10`).
- O log da execução anterior está vazio: o processo é morto antes de escrever qualquer coisa. Por isso também não há erro de aplicação para procurar.
- Recursos no Deployment `nyx-api`: `requests: 16Mi / 50m` e `limits: 24Mi / 200m`. A CPU não é o problema, porque falta de CPU só deixa o processo lento e não gera OOMKill.
- O Deployment está com `ProgressDeadlineExceeded` e nenhuma réplica disponível. **A API está fora do ar**, não só reiniciando de vez em quando.
- O `nyx-postgres` está saudável (`Running`, 0 restarts). Ele não tem `resources` definidos, então o corte não o atingiu.

## Ponto que contradiz o chamado

O chamado diz que o corte mudou os limites "do namespace inteiro". Mas o `nyx-prod` **não tem `LimitRange` nem `ResourceQuota`**. O limite de 24Mi está escrito direto no manifest do Deployment `nyx-api`, aplicado via `kubectl apply`. Então:

- A correção precisa ser feita no manifest de origem do `nyx-api`, seja no repositório ou no pipeline do cliente. Se só criarem ou ajustarem um LimitRange, nada muda, e qualquer patch manual no cluster será desfeito no próximo apply.
- Vale perguntar ao cliente onde o corte foi feito e se outros workloads receberam o mesmo valor. Neste namespace, o postgres ficou sem limite nenhum.

## Próximo passo sugerido (não apliquei nada)

Subir o limite de memória da API para um valor realista para Node.js. Algo como `requests.memory: 128Mi` e `limits.memory: 256Mi` é um ponto de partida razoável. Depois disso, medir o consumo real com `kubectl top` antes de tentar cortar de novo.

Achado paralelo: a senha do banco (`DB_PASSWORD`) está em texto puro no `env` dos dois Deployments. Ela deveria ir para um `Secret`.