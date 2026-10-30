# Brainstorm: dashboard de leitura do cluster (`retrato`)

Sessão com o agente (Claude Code, Opus 5.5) antes dos documentos formais.
Os itens marcados **→ ADR** viraram decisão registrada.

## O problema

Toda triagem começa com a mesma sequência no terminal:

```
kubectl get ns
kubectl -n X get pods
kubectl -n X get deploy
kubectl -n X get svc
kubectl -n X get endpointslices
kubectl -n X get events --sort-by=.lastTimestamp
kubectl -n X describe pod ...
```

São 6 a 10 comandos só para montar o retrato de um namespace. O dashboard
encurta esses primeiros minutos. Ele **não** substitui o terminal.

## Perguntas e respostas

**1. O que é "o retrato"?**
Exatamente o que a skill de triagem (Ticket 02) olha primeiro em cada camada:

- pods (estado, reinícios, motivo da falha);
- deployments (prontos/desejados);
- services (com ou sem endpoint);
- eventos recentes do namespace.

O dashboard é a "primeira chamada" de cada trilha, numa tela só.

**2. Web local, TUI ou desktop?**
- **TUI:** é a mais próxima do terminal, mas tabela larga com quatro seções
  não cabe bem em 80 colunas, e busca/filtro custam mais.
- **Desktop:** empacotamento por SO, que ninguém do time quer manter.
- **Web local em `127.0.0.1`:** o navegador já está aberto, e as tabelas são HTML.

Decisão: web local, um processo, uma página.

**3. Linguagem?** Quem mantém é infraestrutura. **→ ADR-0001**.

**4. Como falar com a API?** Cliente oficial, `kubectl` como subprocesso ou
HTTP direto. O ponto mais difícil é a autenticação: certificado, token e
`exec` plugin (EKS, GKE, OIDC). **→ ADR-0002**.

**5. Como manter a tela atualizada?** Sob demanda, intervalo fixo ou watch.
Com um namespace por vez, o volume é pequeno. O watch traz
reconexão, `resourceVersion` expirado (410) e estado no servidor.
**→ ADR-0003**.

**6. Endpoints ou EndpointSlice?** O `Endpoints` imprime aviso de
descontinuado desde a v1.33. No `nyx-prod` do laboratório, o EndpointSlice
mostrou IPs com 0/2 pods prontos, porque é preciso ler `conditions.ready`.
**→ ADR-0004**.

**7. O que entra na primeira fatia?** O mínimo do enunciado, as três falhas
de ambiente e a garantia de leitura. Logs, YAML e métricas ficam para depois.
**→ ADR-0005**.

**8. "Pronto" é "saudável"?**
Não. O fake-shop **sem** a readiness em `/` (que a skill colocou) ficaria
pronto assim que o gunicorn subisse. O dashboard mostra o que a API afirma
e diz o limite:

- pod/deployment **sem readinessProbe** ganha a marca "pronto = processo de pé";
- a coluna se chama "prontos", não "saudáveis";
- sem métricas e sem chamar a aplicação.

**9. Campo ausente.** O `Deployment` sem réplica pronta não traz
`readyReplicas`. O EndpointSlice sem endpoint traz `endpoints: null`. Ausente
é **zero**, nunca "desconhecido" nem erro. O teste precisa usar objeto real
com o campo ausente.

**10. Como provar o "só leitura"?** Em três lugares, para ninguém ter que
confiar em intenção:

- **código:** um único módulo fala com a API e só tem `list_*`/`read_*`, e um teste falha se aparecer outro verbo;
- **servidor HTTP:** só GET, e o resto devolve 405;
- **RBAC:** ClusterRole `retrato-leitura` só com `get/list/watch`, para quem quiser rodar com credencial própria.

**11. Falhas de ambiente.**
- **Cluster que não responde:** timeout curto e faixa vermelha, sem tela em branco.
- **Credencial expirada:** 401 numa faixa com o que fazer.
- **Permissão negada num recurso:** só aquela seção mostra "sem permissão
  para listar eventos"; as outras seguem. Se a negação for listar
  namespaces, cai para o namespace do contexto e deixa digitar.

## Fora do escopo

Multicluster e troca de contexto (o enunciado proíbe). Qualquer escrita. Logs
de container. Exibir YAML. Métricas (`metrics-server`). Ingress/Gateway. Nós.
Autenticação de usuário do próprio dashboard: ele é local, em `127.0.0.1`, e
usa a credencial de quem o roda.
