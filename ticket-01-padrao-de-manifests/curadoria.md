# Curadoria da skill `padrao-de-manifests`

## 1. A linha entre script e instrução, regra por regra

Critério: vira **script** o que se decide olhando só o YAML, igual para
qualquer manifesto. Vira **instrução** o que exige abrir o projeto, a imagem
ou o histórico. Uma regra pode ter as duas metades. Quando há uma parte que o
Trivy já confere, essa parte fica com o **Trivy**.

| Regra | Nível | Trivy | Script (`confere.py`) | Instrução (SKILL.md) | Por quê |
|---|---|---|---|---|---|
| 1.1 kebab-case | obrig. | — | ✔ | — | regex no nome |
| 1.2 `<cliente>-<amb>` | obrig. | — | ✔ | — | regex no namespace |
| 1.3 quatro rótulos | obrig. | — | ✔ (inclui `instance` = ns, `part-of` = cliente) | — | presença e coerência |
| 1.4 seletor casa | obrig. | — | ✔ (Service, `targetPort`, PDB) | — | cruzamento dentro do arquivo |
| 1.5 owner/runbook | rec. | — | ✔ aviso | qual é o time e o runbook | presença é mecânica; o valor, não |
| 1.6 nome do container | rec. | — | ✔ aviso | — | lista de nomes genéricos |
| 2.1 requests/limits | obrig. | ✔ (LOW) | — | se o **valor** faz sentido (1,5x–2x) | presença é do Trivy; valor exige medição |
| 2.2 probes | obrig. | — | ✔ presença, porta declarada, readiness ≠ liveness | se o **endpoint existe** e se a liveness toca o banco | só o código diz que `/health` existe |
| 2.3 réplicas ≥ 2 em prod | obrig. | — | ✔ | — | número × sufixo do namespace |
| 2.4 RollingUpdate 0/1 | obrig. | — | ✔ | — | campos fixos |
| 2.5 PDB | rec. | — | ✔ aviso (inclui `minAvailable` ≥ réplicas) | — | cruzamento dentro do arquivo |
| 2.6 grace period | rec. | — | — | ✔ a app trata SIGTERM? | só o código ou a imagem diz |
| 3.1 sem `:latest` | proib. | ✔ (KSV-0013, inclusive sem tag) | — | se a tag **existe** e é a do Loom | presença é do Trivy |
| 3.2 securityContext | obrig. | ✔ (9 KSVs) | — | se `readOnlyRootFilesystem` e o UID quebram a app | o Trivy confere os campos; onde a app grava, só o código diz |
| 3.3 segredo em texto | proib. | só ConfigMap (KSV-0109) | ✔ env, URL com credencial, comentário, Secret versionado | **quais** variáveis são credencial e se o nome é o que a app lê | heurística pega o óbvio; o caso `DATABASE_URL` que o kube-news nem lê só aparece no código |
| 3.4 automount false | obrig. | só `true` explícito (KSV-0036) | ✔ campo ausente | — | lacuna medida do Trivy |
| 3.5 SA dedicada | rec. | — | ✔ aviso | se a SA fala com a API | |
| 3.6 host*/privileged | proib. | ✔ (KSV-0008/09/10/17) | — | — | 100% Trivy |
| 3.7 registry interno | obrig. | ✔ com domínio (KSV-0125 + `assets/trivy-data`) | ✔ só imagem **sem** domínio | qual é a imagem espelhada | lacuna medida do Trivy |

**Resultado:** no manifesto barrado, de 25 erros, **14 vêm do Trivy** e **11 do
script** (`execucoes/conferencia-nyx-barrado/confere-saida.txt`). Onde uma
regra é dividida (3.3, 3.4, 3.7), cada caso tem um dono só: o script cobre
exatamente a lacuna medida do Trivy.

## 2. O que o Trivy já cobria (e o que custou descobrir)

O detalhe está em `skill/padrao-de-manifests/references/trivy.md`. O resumo:

- **Cobre por completo:** 3.1 e 3.6.
- **Cobre a presença:** 2.1 e os campos da 3.2.
- **Cobre em parte, com lacunas que ninguém vê sem testar:**
  - 3.4: a KSV-0036 só dispara com `true` explícito, e campo ausente passa;
  - 3.7: a KSV-0125 ignora imagem sem domínio, e sem a lista de registries
    configurada marca **toda** imagem do parque como não confiável;
  - 3.3: só pega senha em ConfigMap. Nem o `trivy fs --scanners secret` vê
    `postgres://nyx:s3nh4-do-banco@...`.
- **Classifica obrigatória como LOW:** 2.1 e partes da 3.2. Por isso o script
  roda o Trivy com `--severity LOW,...`.
- **Pede mais que o padrão:** KSV-0021 (`runAsGroup`) e 0030/0104
  (`seccompProfile`) viraram AVISO. O modelo declara os dois mesmo assim,
  porque o Pod Security `restricted` cobra `seccompProfile`.
- **Falso positivo:** KSV-01010 marca `HTTP_PORT: "8080"` em ConfigMap como
  "passaporte". Está ignorado em `assets/trivyignore.yaml`, com o motivo.

O que o trabalho anterior fazia de errado: o `check_padrao.py` reimplementava
2.1, 3.1, 3.2 e 3.6. Na skill, essas regras saíram do script.

## 3. O que ficou no corpo e o que virou arquivo sob demanda

| Arquivo | Quando é lido | Conteúdo |
|---|---|---|
| `SKILL.md` (~110 linhas) | sempre que a skill dispara | os dois modos, o passo a passo, a tabela "o que o script não decide", os limites |
| `scripts/confere.py` | executado, não lido | Trivy + regras que o Trivy não cobre |
| `references/escrita.md` | só no modo escrita | migração no start, app sem endpoint de saúde, senha fora do manifesto, `readOnlyRootFilesystem`, valores de partida |
| `references/regras.md` | quando precisar do texto de uma regra | tabela das 19 regras com a armadilha de cada uma |
| `references/trivy.md` | quando precisar saber de onde veio um achado | KSV → regra, configuração, lacunas |
| `assets/modelo.yaml` | no modo escrita | esqueleto que já passa no `confere.py` com zero erro |
| `assets/trivy-data/`, `assets/trivyignore.yaml` | pelo script | lista de registries confiáveis e a única exclusão |

O corpo tem só o que muda o comportamento em toda execução. A conferência,
que é o uso mais frequente, não precisa abrir nenhuma referência. As duas
execuções de conferência abriram `regras.md` uma vez, para montar a tabela.

## 4. O que ficou de fora e por quê

| Fora | Por quê |
|---|---|
| **Bloco 4 inteiro** (vocabulário: Pod, ReplicaSet, Deployment, Service, port × targetPort, Endpoints, ConfigMap, probes) | Existe para quem está chegando na plataforma, e o modelo já sabe isso. Cada linha custaria contexto em toda execução sem mudar nenhuma decisão. O único ponto do bloco que muda conduta (Endpoints descontinuado, campo ausente) foi para a skill de triagem, que é onde ele importa |
| **Justificativas narrativas das regras** ("cada regra nasceu de um incidente", "o plantão agradece") | Não mudam o que o agente faz. A regra fica, a história sai |
| **Histórico de revisões do wiki** | Só a versão vigente importa para conferir |
| **Processo de exceção** (`excecao.metacortex.io/<regra>` com validade, da implementação inicial) | É processo de PR, não regra de manifesto, e foi uma proposta minha, não está no padrão. Empacotar daria ao agente um jeito de "aprovar" exceção sozinho. A skill só diz que AVISO vira justificativa escrita |
| **Os nove achados da revisão do padrão como texto** | Viraram uma coluna "armadilha" de uma linha em `regras.md`. A evidência completa continua em `referencia/docs/` |
| **`kubectl apply --dry-run=server`** | Útil (pega Pod Security e schema), mas exige cluster e encosta no apiserver. Fica na CI, não na skill |
| **Laboratório kind** | Evidência para a revisão do padrão, não método de conferência |

## 5. Permissões

O frontmatter declara em `allowed-tools`:

```
Read, Grep, Glob, Write,
Bash(python3 *confere.py*), Bash(trivy config *),
Bash(git clone --depth 1 *), Bash(docker image inspect *), Bash(docker pull *)
```

- **Leitura** (`Read`, `Grep`, `Glob`): o manifesto, o projeto clonado e as referências.
- **`Write`**: só o modo escrita precisa (os manifests e o YAML corrigido em `/tmp`).
- **Bash restrito por prefixo**: o script, o Trivy em modo `config` (não
  `image`, não `fs`), `git clone` raso e inspeção de imagem.
- **Fora**: `kubectl` (a skill não toca cluster), `docker run`, `rm`, `curl`,
  rede genérica.

Duas observações honestas sobre as execuções:

1. As sessões gravadas rodaram com `--allowedTools "... Bash(docker:*)"` na
   linha de comando, mais amplo que o frontmatter. Por isso o agente pôde
   fazer `docker run` da imagem com `--read-only --user 10001` para provar a
   raiz somente leitura. O resultado foi útil, e virou passo **opcional** no
   SKILL.md ("se o usuário permitir"). Mas `docker run` **não** entrou no
   `allowed-tools`: subir container é efeito colateral, e o usuário deve ser
   perguntado.
2. `allowed-tools` **pré-aprova**; ele não **restringe**. Uma ferramenta fora
   da lista ainda pode ser usada, com pedido de permissão ao usuário. A
   garantia de "não aplica no cluster" está no texto da skill e na ausência de
   `kubectl` na lista, não num bloqueio. Para bloqueio de verdade, ver como o
   Ticket 02 faz (RBAC + `deny`).

## 6. Saídas ruins e o que eu faria diferente

- **v1 da conferência:** YAML com âncora entre documentos (inválido), correção
  não conferida, UID "não verificado". Corrigido na v2. O detalhe está em `origem.md`.
- **Custo do modo escrita:** US$ 1,09 e 3 min, com 42 turnos, dos quais ~10
  gastos lendo a `referencia/` para copiar o estilo de owner e runbook.
  Faria diferente: pôr `owner`/`runbook` como pergunta explícita ao usuário,
  em vez de deixar o agente procurar convenção no repositório.
- **O script não pega "variável que a app não lê"** (`DATABASE_URL` no kube-news).
  Não dá para pegar: depende do código. Fica na instrução, e as duas
  conferências pegaram.
- **Heurística de 3.3 por nome** (`passw|secret|token|...`) dá falso negativo
  com nomes criativos e falso positivo com `TOKEN_TTL`. Aceitei: a instrução
  manda conferir quais variáveis são credencial lendo o código.
