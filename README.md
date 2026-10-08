# metacortex — manifests de referência

Resposta ao desafio técnico do **Padrão de Manifests da Metacortex** (revisão
de 2026-07-29, [enunciado aqui](docs/padrao-de-manifests.md)).

O repositório tem quatro entregas:

1. **Manifests** de um workload real (API HTTP, worker de fila e CronJob) que
   atendem a todas as regras obrigatórias e recomendadas, em `nyx-prod` e `nyx-dev`.
2. **Verificador automático** das regras que o Trivy não conhece, com um
   teste negativo para cada uma.
3. **Validação em cluster real** (kind, Kubernetes v1.36), com laboratório
   reproduzível.
4. **[Revisão do próprio padrão](docs/revisao-do-padrao.md)**: nove achados em
   que o wiki, seguido ao pé da letra, não entrega o que promete. Cada um tem
   evidência.

## Estrutura

| Caminho | O que é |
| --- | --- |
| `manifests/nyx-prod/` | Produção: API + worker + CronJob, com PDBs e SAs dedicadas |
| `manifests/nyx-dev/` | A API em dev. Muda só o que o padrão deixa mudar fora de prod |
| `scripts/check_padrao.py` | Verificador dos Blocos 1–3 e do processo de exceção |
| `scripts/validate.sh` | Roda localmente o mesmo que a CI |
| `exemplos/reprovados/` | Sete anti-padrões. A 1ª linha de cada um diz em que regras **deve** reprovar |
| `tests/` | Garante que cada anti-padrão reprova exatamente no que declara, e que `manifests/` passa limpo |
| `.trivy/` | Configuração do Trivy: `registry.metacortex.io` como registry confiável |
| `.trivyignore.yaml` | Um único falso positivo ignorado, com motivo e escopo |
| `lab/` | Laboratório em kind que reproduz os achados da revisão |
| `docs/conformidade.md` | Regra → arquivo → quem verifica |
| `docs/revisao-do-padrao.md` | Achados sobre o padrão, com saída do cluster |

## Validar antes do PR

Requisitos: Python 3 com PyYAML. Trivy e kubectl são opcionais localmente; a
CI sempre roda os dois.

```bash
bash scripts/validate.sh
```

Etapas:

1. testes do verificador;
2. verificador sobre `manifests/`;
3. Trivy com **todas** as severidades (ver achado 6c);
4. `kubectl apply --dry-run=server` (só roda se houver um cluster acessível).

Saída do verificador num manifesto ruim:

```
$ python3 scripts/check_padrao.py exemplos/reprovados/02-service-sem-endpoint.yaml
ERRO  1.4  ... Service/nyx-api-seletor-errado — nenhum pod do namespace casa com o seletor
           {'app.kubernetes.io/name': 'nyxapi', ...} — o Service subiria sem endpoint
ERRO  1.4  ... Service/nyx-api-porta-errada — targetPort 'web' nao existe em nenhum container selecionado
```

ERRO reprova (regra obrigatória ou proibida). AVISO não reprova (regra
recomendada; a justificativa vai no PR). `--github` emite anotações para o
GitHub Actions.

## CI

`.github/workflows/manifests.yml` roda dois jobs:

- **padrao**: testes, verificador e Trivy;
- **admissao**: sobe um kind e faz `--dry-run=server` dos manifests. Pega o que
  a análise estática não vê: schema estrito, validação do apiserver e Pod
  Security `restricted`.

## Laboratório

```bash
bash lab/lab.sh          # cria o cluster kind "metacortex-lab" e reproduz os achados
bash lab/lab.sh limpar   # apaga o cluster
```

Usa uma imagem pública (`nginx-unprivileged`) para que os Pods subam de
verdade. Por isso fica fora de `manifests/`. Os manifests de referência
também são aplicados: os Pods são **admitidos** sob Pod Security
`restricted` e param em `ImagePullBackOff`, porque `registry.metacortex.io`
só existe dentro do parque.

## Exceções

A seção "Exceções" do wiki vira uma anotação versionada junto com o objeto,
e o verificador a respeita:

```yaml
metadata:
  annotations:
    excecao.metacortex.io/2.3: "validade=2026-12-31; aprovacao=<link do PR com aprovação de S&C>"
```

Uma exceção válida transforma o ERRO em AVISO. Vencida, ela volta a reprovar
sozinha. Regra proibida não aceita exceção. Detalhes no
[achado 8](docs/revisao-do-padrao.md#8-falta-mecanismo-para-registrar-exceção-com-validade).

## Segredos

Por causa da regra 3.3, nenhum `Secret` está versionado. Estes precisam existir
no namespace antes do deploy e são criados pelo cofre da plataforma, fora do Git:

| Secret | Chave | Usado por |
| --- | --- | --- |
| `nyx-db` | `url` | `nyx-api` e `nyx-reconcile` → `DATABASE_URL` |
| `nyx-queue` | `url` | `nyx-worker` → `QUEUE_URL` |

## Para criar um workload novo

Copie `manifests/nyx-prod/` e troque `nyx` pelo cliente e o componente pelo
seu. Rode `scripts/validate.sh`. O que sobrar para a revisão humana está no
fim de [conformidade.md](docs/conformidade.md#o-que-continua-sendo-revisão-humana).
