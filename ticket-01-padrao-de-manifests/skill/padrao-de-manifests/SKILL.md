---
name: padrao-de-manifests
description: >-
  Escreve ou confere manifests YAML de Kubernetes contra o Padrão de Manifests da
  Metacortex (nomenclatura, rótulos, seletor, requests/limits, probes, réplicas
  em prod, securityContext, segredos, registry interno). Use ANTES de um
  manifesto subir: "revisa esse deployment", "esse manifesto está no padrão?",
  "cria os manifests do projeto X", "gera um Deployment/Service". NÃO use para
  investigar algo que já está rodando e quebrou no cluster (pod reiniciando,
  service sem endpoint em produção, 503) — isso é triagem de cluster.
allowed-tools: Read, Grep, Glob, Write, Bash(python3 *confere.py*), Bash(trivy config *), Bash(git clone --depth 1 *), Bash(docker image inspect *), Bash(docker pull *)
---

# Padrão de Manifests da Metacortex

Dois modos. Descubra qual pelo pedido:

- **Conferência** (o mais comum): o usuário tem um YAML e quer saber o que viola.
- **Escrita**: o usuário tem um projeto e quer os manifests já no padrão.

Nos dois, o trabalho tem duas metades que não se misturam:

1. **Mecânica**: `scripts/confere.py`. Roda o Trivy e as regras que o Trivy não
   conhece. Não confira à mão o que o script confere.
2. **Julgamento**: o que só se decide lendo o projeto empacotado. Está nas
   seções "o que o script não decide" abaixo. É onde mora o valor da revisão.

## Conferência

1. Rode o script sobre o arquivo ou diretório:
   ```bash
   python3 <dir-da-skill>/scripts/confere.py <caminho>
   ```
   Cada linha traz nível (`ERRO` reprova, `AVISO` é regra recomendada), a regra
   do padrão e a origem (`[trivy]` ou `[script]`). Se aparecer
   `NAO VERIFICADO: Trivy indisponivel`, diga isso no relatório. Não declare
   2.1, 3.1, 3.2 ou 3.6 como conformes.
2. **Ache o projeto da imagem.** Sem o código não se avaliam as probes, as
   variáveis e os caminhos graváveis. Se o usuário não indicou o repositório,
   pergunte. Projetos conhecidos: `nyx` → github.com/KubeDev/kube-news,
   `orion` → github.com/KubeDev/fake-shop, `helio` → github.com/KubeDev/encontros-tech.
   Clone com um comando só, sem `cd`, `mktemp` ou `&&`, para não esbarrar em
   pedido de permissão: `git clone -q --depth 1 <url> /tmp/<projeto>-src`.
   Depois, só leia.
3. **Ache a imagem.** Se a imagem interna (`registry.metacortex.io/...`) não
   estiver acessível, inspecione a imagem pública de origem que o Loom espelha
   (ex.: `fabricioveronez/<projeto>:<tag>`) para UID, comando e workdir. Só
   marque "não verificado" se nenhuma das duas for acessível.
4. Faça a conferência de julgamento (abaixo).
5. Entregue um relatório **agrupado por regra**, não por linha do script:
   `regra · obrigatória/recomendada · o que está errado · como corrigir`.
   Junte as várias linhas KSV de uma mesma regra numa só. Feche com o YAML
   corrigido.
6. **Confira a própria correção**: grave o YAML corrigido em `/tmp/` e rode
   `confere.py` nele. Informe o resultado; a meta é zero ERRO. Não entregue
   correção sem conferir.

Ao escrever YAML, nunca use âncoras (`&x`/`*x`) entre documentos separados
por `---`: âncora não atravessa documento, e o arquivo deixa de ser válido.
Repita os rótulos.

**Se o `confere.py` não puder rodar** (sem Bash, sem Python, sem Trivy), diga
isso no começo da resposta: "conferência mecânica NÃO feita". Depois confira à
mão, pelo menos 1.1, 1.3 (`managed-by` ∈ `platform|argocd|helm`, `part-of` =
cliente) e 3.3. Nunca apresente YAML como "conforme ao padrão" sem uma das duas
conferências. Vale também para objeto sem pod (RBAC, ConfigMap): o Bloco 1
se aplica a todo objeto.

### Conferência: o que o script não decide

Para cada item, cite o arquivo do projeto que sustenta a conclusão.

| Regra | Pergunta | Onde olhar no projeto |
|---|---|---|
| 2.2 | As probes apontam para endpoints que **existem**? Readiness e liveness checam coisas diferentes? A liveness depende do banco? | rotas do servidor (`app.get('/health')`, `@app.route`), middleware |
| 2.2 | A porta da probe e o `containerPort` são a porta em que o processo escuta? | `listen(...)`, `--bind`, `CMD`/entrypoint da imagem |
| 3.3 | Quais variáveis são credencial? O nome que o manifesto usa é o que a aplicação **lê**? | `process.env.X`, `os.getenv('X')`, README |
| 3.2 | `readOnlyRootFilesystem: true` quebra a aplicação? Onde ela grava? | diretórios de cache, `/tmp`, `PROMETHEUS_MULTIPROC_DIR`, uploads |
| 3.2 | O UID da imagem é compatível com `runAsUser`? | `docker image inspect <img> --format '{{.Config.User}}'` |
| 2.1 | Os valores fazem sentido? Limite de memória entre 1,5x e 2x o consumo em regime | se não houver medição, diga que o valor é chute inicial |
| 2.6 | A aplicação trata SIGTERM? Precisa de mais de 30s para drenar? | servidor (gunicorn trata; `node server.js` sem handler não) |
| 3.1 | A tag existe e é a que o Loom publicou? | registry, release |

## Escrita

1. Leia o projeto (tabela acima) e a imagem antes de escrever qualquer YAML.
   Anote: porta, endpoints de saúde (ou a falta deles), variáveis lidas,
   credenciais, onde grava, UID, comando de start, se roda migração.
2. Parta de `assets/modelo.yaml`. Ele já atende tudo o que é mecânico. Detalhes
   e decisões típicas (migração no start, app sem endpoint de saúde, senha que
   não pode ir no YAML) estão em `references/escrita.md`. Leia-o no modo escrita.
3. Um arquivo por objeto, numerado pela ordem de aplicação (`00-namespace`,
   `10-serviceaccount`, `20-configmap`, `30-deployment-<comp>`,
   `31-service-<comp>`, `32-pdb-<comp>`...).
4. Rode `confere.py` sobre o diretório gerado. A meta é **zero ERRO**. Os AVISOS
   que sobrarem viram justificativa escrita. Opcional, se o usuário permitir:
   subir a imagem localmente como o manifesto a roda
   (`docker run --rm --read-only --user 10001:10001 --cap-drop ALL --tmpfs ...`)
   para provar que a raiz somente leitura e o UID não quebram a aplicação.
   Pare o container ao fim.
5. Feche com uma seção **Decisões** curta: cada ponto em que você escolheu algo
   que o padrão não dita (probe sem endpoint de saúde, onde roda a migração,
   valores de recurso sem medição) e o que o time do cliente precisa confirmar.

## Limites

- Esta skill não aplica nada no cluster: nada de `kubectl apply`, nem com
  `--dry-run`, a menos que o usuário peça explicitamente.
- Nunca escreva valor de segredo em arquivo. Gere o Secret por comando
  (`kubectl create secret ... --dry-run=client -o yaml` fora do repositório) e
  referencie com `secretKeyRef`.
- Imagem pública não entra direto: vira `registry.metacortex.io/<cliente>/<nome>:<tag>`,
  espelhada pelo Loom. Diga isso no relatório.
- Texto completo das regras, com as armadilhas conhecidas:
  `references/regras.md`. O que o Trivy cobre e com qual ID:
  `references/trivy.md`. Consulte só quando precisar.
