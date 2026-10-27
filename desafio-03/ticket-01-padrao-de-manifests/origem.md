# Origem da skill `padrao-de-manifests`

**Agente:** Claude Code 2.1.311. **Modelo:** Claude Opus 5.5 (`claude-opus-5-5`)
em todas as etapas, inclusive nas sessões de execução.
**Ferramenta de empacotamento:** a própria sessão do Claude Code. Os arquivos
foram escritos com as ferramentas de edição do agente, sem gerador de skill.

## Fluxo que deu origem

A skill não foi escrita de cabeça. Ela saiu de três rodadas de trabalho, nesta
ordem.

### 1. Trabalho manual com o agente (`trabalho-anterior/`)

Antes da skill, o padrão foi aplicado à mão com o agente:

- manifests de referência do nyx em `nyx-prod` e `nyx-dev`;
- um verificador (`check_padrao.py`) com teste negativo por regra;
- um laboratório em kind que reproduz o que o padrão promete e não entrega.

Desse trabalho saíram nove achados sobre o próprio padrão
(`trabalho-anterior/docs/revisao-do-padrao.md`). Os mais importantes viraram
instrução da skill:

- a 3.2 colada no nível do Pod é recusada pelo apiserver;
- sem `seccompProfile`, o Pod Security `restricted` barra o pod;
- o caso silencioso da 1.4 é o Service, não o Deployment;
- o Trivy classifica regras obrigatórias como LOW.

O que esse trabalho **não** fazia era separar o que o Trivy já cobria. O
`check_padrao.py` reimplementava 2.1, 3.1, 3.2 e 3.6, todas cobertas pelo
catálogo. Era exatamente o que o ticket pede para não fazer.

### 2. Medição do Trivy no manifesto barrado

Nesta sessão, antes de escrever o script da skill, o Trivy v0.74.0 rodou sobre
o manifesto barrado do nyx, e depois sobre manifests de teste com
`hostNetwork`, `privileged`, imagem sem tag e imagem de outro registry. O que
saiu daí:

| Medição | Resultado | Consequência na skill |
|---|---|---|
| Trivy no barrado | pega 2.1, 3.1 e 3.2 (16 achados) | o script **não** confere essas regras |
| Trivy no barrado | **não** pega 1.1, 1.3, 1.4, 2.2, 2.3, 2.4, 3.3, 3.4 | o script confere essas |
| `trivy fs --scanners secret` | não vê `postgres://nyx:s3nh4-do-banco@...` | 3.3 fica no script |
| KSV-0036 (automount) | só dispara com `true` explícito; ausente passa | 3.4 fica no script |
| KSV-0125 (registry) | ignora imagem sem domínio (`nginx:1.27`) | o script cobre só essa lacuna da 3.7 |
| KSV-0013 | pega imagem **sem tag**, além de `:latest` | 3.1 fica 100% no Trivy |
| KSV-0021, 0030, 0104 | pedem mais que o texto da 3.2 | rebaixadas a AVISO, para o script não barrar o que o padrão não exige |

O código das regras foi lido em `~/.cache/trivy/policy/.../*.rego` para
confirmar o comportamento da KSV-0036.

Com essa medição, o `check_padrao.py` (475 linhas) foi recortado no
`scripts/confere.py`. O recorte tirou o que o Trivy cobre, tirou o processo de
exceção (ver curadoria) e passou a chamar o Trivy e traduzir cada KSV para a
regra do padrão. A suíte de anti-padrões do trabalho anterior foi reaproveitada
como teste (`tests/test_confere.py`). Cada anti-padrão reprova exatamente nas
regras que declara.

### 3. Leitura dos projetos e das imagens

Os três repositórios foram clonados e lidos, e as imagens publicadas foram
inspecionadas. Daí saíram as decisões de escrita que viraram
`references/escrita.md`:

- O fake-shop roda `flask db upgrade` no `entrypoint.sh`. Com `replicas >= 2`,
  as réplicas concorrem, e por isso a migração vai para um Job.
- O fake-shop não tem endpoint de saúde. `/` lê do banco (bom para readiness) e
  `/metrics` não toca o banco (bom para liveness).
- O fake-shop tem `os.getenv('DB_PASSWORD', 'Pg1234')`: sem o Secret, ele sobe
  com a senha do código em vez de falhar.
- A imagem do fake-shop já roda como UID 10001 e espera `/tmp/metrics` pronto.
  Um `emptyDir` em `/tmp` esconde esse diretório.
- O kube-news lê `DB_HOST`/`DB_USERNAME`/`DB_PASSWORD`, e não `DATABASE_URL`.
  O manifesto barrado passa uma variável que a aplicação nem lê.

### 4. Execução em sessão limpa e iteração

A skill foi instalada como skill de projeto (`.claude/skills/padrao-de-manifests`,
link para `skill/`) e executada com `claude -p` em sessões novas, **sem citar o
nome da skill no pedido**. Nas três execuções, ela disparou sozinha pela
descrição.

A primeira conferência (v1) teve três defeitos, que mudaram a skill para a v2:

| Defeito na v1 | Mudança no SKILL.md (v2) |
|---|---|
| O YAML corrigido usava âncora `&labels` entre documentos `---`, o que gera YAML inválido | regra explícita: não usar âncora entre documentos |
| Entregou a correção sem rodar `confere.py` nela ("Não rodei o confere.py sobre o trecho corrigido") | passo 6: conferir a própria correção antes de entregar |
| Deixou o UID como "não verificado", tendo a imagem pública ao alcance | passo 3: inspecionar a imagem de origem que o Loom espelha |
| Gastou quatro turnos com `git clone` barrado por permissão (`mktemp`, `cd &&`) | comando de clone único e literal no passo 2 |

O resultado das duas versões está em `execucoes/conferencia-nyx-barrado/v1` e `v2`.

### 5. Iteração vinda do Ticket 04 (v3)

Durante o dashboard, a skill disparou para escrever uma **ClusterRole**, numa
sessão sem Bash. Ela não pôde rodar o `confere.py`, não avisou, e entregou
`managed-by: kubectl`, que viola a 1.3 que ela mesma aplica
(`../ticket-04-dashboard-do-cluster/observacao-skills/03-clusterrole-do-dashboard.md`).
A v3 acrescentou ao SKILL.md: "se o `confere.py` não puder rodar, diga
'conferência mecânica NÃO feita' e confira à mão 1.1, 1.3 e 3.3; o Bloco 1 vale
para todo objeto". A mesma pergunta, depois da correção, saiu com o aviso e
com `managed-by: platform` (`.../03b-clusterrole-apos-correcao.md`).
