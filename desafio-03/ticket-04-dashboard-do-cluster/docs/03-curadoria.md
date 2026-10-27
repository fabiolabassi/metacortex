# Curadoria: retrato

Arco seguido: [brainstorm](00-brainstorm.md) → [PRD](01-PRD.md) →
[TRD](02-TRD.md) + [5 ADRs](adr/) → OpenSpec (proposta, 3 specs, design,
tarefas) → implementação → validação contra o kind → arquivamento
(`openspec/changes/archive/2026-10-26-retrato-do-namespace/`).

## 1. Onde a spec precisou ser corrigida durante a implementação

Todas as correções vieram da **validação com captura de tela contra o
cluster real**, não dos testes de unidade. As capturas mostraram o que o
JSON não mostrava.

| # | O que a spec/TRD dizia | O que a tela mostrou | Correção |
|---|---|---|---|
| 1 | spec `falhas-de-ambiente`: com permissão negada, só a seção afetada mostra a negação; TRD: faixa de "leitura parcial" | com o papel restrito, a faixa dizia "não pode listar **1** tipo(s)", mas eram dois. O erro de EndpointSlice chega **dentro** das linhas de Service (coluna endpoint), não como seção | a faixa passou a **nomear** os recursos negados ("events, endpointslices") e a contar também os erros embutidos nas linhas |
| 2 | spec: sem permissão de listar namespaces, usa o do contexto "com aviso" | o aviso aparecia e sumia na primeira atualização, porque o redesenho limpava todas as faixas | lugar próprio para o aviso de namespace (`#faixa-ns`), que o ciclo não apaga |
| 3 | TRD §4: a marca "pronto = processo de pé" vale para container sem readinessProbe | o pod **`Succeeded`** do Job de migração do fake-shop ganhou a marca, o que é ruído: pod terminado não recebe tráfego | a marca vale só para pod `Running`. A spec já dizia "pod **pronto**"; o código tinha generalizado (ver §2) |
| 4 | TRD §4: dica "nenhum pod casa com o seletor `<seletor>`" | a dica saiu como dict Python: `{'app': 'nyx-api'}` | formato `app=nyx-api`, o mesmo do `kubectl -l` |
| 5 | ADR-0004: `ready` nulo conta como pronto | confirmado na API (`discovery.k8s.io/v1`); não apareceu no laboratório | mantido, com teste sintético (`test_ready_nulo_conta_como_pronto`) |

## 2. O que o agente entendeu diferente do que estava escrito

- **"Pronto sem readinessProbe"** foi implementado como "qualquer pod sem
  readinessProbe", e não "pod **pronto** sem readinessProbe", como dizia a
  spec. O pod do Job, terminado, ganhou a marca. Só a tela pegou isso.
- **"Uma faixa por erro de ambiente"** foi implementado contando seções. O TRD
  falava em "tipo de recurso", e o EndpointSlice não é seção. A divergência
  só apareceu com um papel que nega exatamente esse recurso.
- Fora esses dois casos, o código seguiu o TRD. As outras quatro correções da
  §1 são da spec, não de leitura divergente.

## 3. Saídas ruins e incidentes registrados

- **Imagem do kube-news "incomplete (1/10)" no kind.** O `kind load` de um
  índice multi-plataforma importou só o índice, e o kubelet tentou o pull de
  `registry.metacortex.io` mesmo com `IfNotPresent`. Foi **diagnosticado pela
  skill de triagem numa sessão limpa** (`observacao-skills/02-triagem-nyx-dev.md`):
  "DNS não resolve o registry". A causa correta no nível do cluster. A causa
  no nível do laboratório (imagem incompleta no containerd) foi achada à
  parte, com `ctr images check`. O `lab/subir-workloads.sh` agora reconstrói a
  imagem com uma camada `LABEL` (plataforma única) e remove a versão anterior
  do nó. Uma primeira tentativa com só `FROM` não funcionou: o BuildKit
  reaproveitou o mesmo ID.
- **`pkill -f` derrubou o próprio shell** que rodava o comando, porque o padrão
  casava com a linha de comando. Virou o `lab/captura.sh`, que guarda o PID.
- **Port-forward bloqueado** pela permissão automática do agente. A prova de
  que os dois workloads atendem ficou pela readiness: a do fake-shop é `GET /`,
  que lê o banco, então pod pronto = banco e esquema migrado respondendo.

## 4. Justificativa estendida de cada decisão em aberto

Cada ADR tem a tabela completa. Aqui fica o resumo do que se ganha e do que
se perde com o caminho escolhido e com dois descartados.

### Linguagem e stack ([ADR-0001](adr/0001-stack-python-stdlib-http-e-pagina-unica.md))

| | Ganha | Perde |
|---|---|---|
| **Python + `http.server` + HTML sem build** ✔ | uma dependência; o time de infra lê o projeto inteiro; a mesma linguagem do Ticket 03 | UI escrita à mão; sem componentes prontos |
| Go + client-go | binário único; o client-go é a referência | o time não mantém Go; toolchain no pipeline; client-go (informers) maior que o problema |
| Node + React | ecossistema de UI | dois mundos (Node + build); centenas de pacotes numa estação com credencial de produção |

### Acesso à API ([ADR-0002](adr/0002-cliente-oficial-python.md))

| | Ganha | Perde |
|---|---|---|
| **Cliente oficial** ✔ | autenticação completa (certificado do `platform-ro`, token, `exec` plugin), contexto corrente, modelos com `None` explícito, 401/403 distintos | dependência que acompanha a versão do Kubernetes |
| `kubectl` subprocesso | herda tudo do kubectl | um processo por listagem; distinguir 401/403/timeout é parsear texto; depende do kubectl instalado |
| HTTP direto | status HTTP limpo; zero dependência | reimplementar kubeconfig, CA, certificado e **exec plugin**: código de autenticação próprio numa ferramenta de produção |

### Atualização ([ADR-0003](adr/0003-atualizacao-por-intervalo-fixo.md))

| | Carga no apiserver | Complexidade | Atraso |
|---|---|---|---|
| **Intervalo de 10 s** ✔ | 0,5 req/s por tela, só no namespace aberto; zero com aba oculta | baixa, sem estado | ≤ 10 s |
| Sob demanda | mínima | mínima | ilimitado: retrato velho sem aviso |
| Watch | menor em regime | 5 streams, reconexão, 410 Gone, cache, push ao navegador | ~1 s |

### Fonte dos endpoints ([ADR-0004](adr/0004-endpointslice.md))

| | Ganha | Perde | Vida útil |
|---|---|---|---|
| **EndpointSlice** ✔ | `ready` por endereço (pega o `nyx-prod`: IPs listados, 0 prontos); porta por slice (pega `targetPort` errado) | agrupar slices por rótulo | é a API do kube-proxy |
| Endpoints | um objeto por Service | aviso de descontinuado; trunca em 1000; quebra na remoção | até a remoção |
| Inferir por seletor × pods | independe dos dois objetos | reimplementa o controller e erra em `targetPort` nomeado | sempre, mas mostra o que **deveria** ser |

### Recorte da primeira fatia ([ADR-0005](adr/0005-recorte-da-primeira-fatia.md))

| | Ganha | Perde |
|---|---|---|
| **Mínimo + três falhas + só leitura** ✔ | encurta os primeiros minutos; validado inteiro contra o cluster | logs ainda no terminal |
| Mínimo + logs | cobre a trilha Pod da triagem | streaming, `pods/log`, segredo em log; dobra o teste |
| Só o caminho feliz | sai mais rápido | é o que o enunciado proíbe; some quando o cluster está ruim |

## 5. O quanto o dashboard afirma sobre saúde

O dashboard afirma só o que a API afirma, com o nome que a API usa:

- **"prontos"**, nunca "saudáveis";
- container **sem readinessProbe** ganha a marca **"pronto = processo de pé"**
  (Postgres dos chamados, e o fake-shop se não tivesse a readiness em `/` que a
  skill do Ticket 01 colocou);
- Service com IPs mas sem endereço pronto aparece **vermelho** (`0/2 prontos`);
- nada de métrica, nada de chamar a aplicação: o dashboard não sabe se o
  `/ready` do kube-news consulta o banco (ele não consulta).
