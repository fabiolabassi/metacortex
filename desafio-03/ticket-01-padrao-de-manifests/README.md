# Ticket 01: skill do padrão de manifests

Skill que aplica o [Padrão de Manifests da Metacortex](anexo-padrao-de-manifests.md)
em dois modos: **conferência** (apontar o que um manifesto viola) e **escrita**
(gerar manifests novos a partir de um projeto). O que é mecânico virou script,
que chama o Trivy e cobre o que ele não cobre. O que exige ler o projeto virou
instrução.

## Onde está cada item pedido

| Entregue | Onde |
|---|---|
| **A skill completa** (corpo, script e arquivos de apoio) | [`skill/padrao-de-manifests/`](skill/padrao-de-manifests/) |
| ↳ corpo | [`SKILL.md`](skill/padrao-de-manifests/SKILL.md) |
| ↳ script | [`scripts/confere.py`](skill/padrao-de-manifests/scripts/confere.py), testado em [`tests/test_confere.py`](tests/test_confere.py) |
| ↳ apoio sob demanda | [`references/`](skill/padrao-de-manifests/references/) (regras, escrita, trivy) e [`assets/`](skill/padrao-de-manifests/assets/) (modelo, config do Trivy) |
| **A origem da skill** (fluxo, como foi produzida, ferramenta) | [`origem.md`](origem.md) |
| **Saída real: modo escrita** (fake-shop, orion-prod) | [`execucoes/escrita-fake-shop/`](execucoes/escrita-fake-shop/): [`manifests/`](execucoes/escrita-fake-shop/manifests/), [`relatorio.md`](execucoes/escrita-fake-shop/relatorio.md), [`confere-saida.txt`](execucoes/escrita-fake-shop/confere-saida.txt), [`trilha.txt`](execucoes/escrita-fake-shop/trilha.txt) |
| **Saída real: conferência do manifesto barrado** | [`execucoes/conferencia-nyx-barrado/`](execucoes/conferencia-nyx-barrado/): entrada [`nyx-api-barrado.yaml`](execucoes/conferencia-nyx-barrado/nyx-api-barrado.yaml), saída do script [`confere-saida.txt`](execucoes/conferencia-nyx-barrado/confere-saida.txt), relatório [`v1`](execucoes/conferencia-nyx-barrado/v1/relatorio.md) e [`v2`](execucoes/conferencia-nyx-barrado/v2/relatorio.md), YAML corrigido [`v2/nyx-api-corrigido.yaml`](execucoes/conferencia-nyx-barrado/v2/nyx-api-corrigido.yaml) |
| **Curadoria** (script × instrução por regra, o que o Trivy cobria, corpo × sob demanda, o que ficou de fora, permissões) | [`curadoria.md`](curadoria.md) |

Cada pasta de execução tem a sessão completa (`sessao.jsonl`, do
`claude -p --output-format stream-json`) e um resumo dela (`trilha.txt`), com a
skill que disparou, cada ferramenta chamada, tokens, custo e tempo.

## Resumo das execuções

As sessões rodaram limpas, com `claude -p` e **sem citar a skill no pedido**.

| Execução | Skill disparou sozinha? | Resultado | Tempo | Custo |
|---|---|---|---|---|
| Conferência v1 | sim | 11 regras violadas; achou `DATABASE_URL` que o kube-news não lê. **Defeitos:** YAML corrigido inválido, correção não conferida | 72 s | US$ 0,56 |
| Conferência v2 (skill corrigida) | sim | mesmas 11 regras; correção conferida (0 erro); imagem inspecionada e executada | 121 s | US$ 0,61 |
| Escrita fake-shop | sim | 8 objetos, `confere.py` com 0 erro e 0 aviso; migração em Job; probes sem endpoint de saúde; senha em Secret fora do Git | 179 s | US$ 1,09 |

## Como usar

A skill está instalada como skill de projeto em
`.claude/skills/padrao-de-manifests`, um link para `skill/padrao-de-manifests`.
Basta abrir o Claude Code na raiz do repositório e pedir, por exemplo, "esse
manifesto está no padrão da casa?".

O script também roda sozinho. Requer Python 3 com PyYAML, e Trivy para as
regras 2.1, 3.1, 3.2 e 3.6:

```bash
python3 skill/padrao-de-manifests/scripts/confere.py execucoes/conferencia-nyx-barrado/nyx-api-barrado.yaml
python3 -m unittest discover -s tests -v
```

Códigos de saída: 0 sem erro, 1 com erro de padrão, 2 em erro de uso.

## Trabalho anterior

[`trabalho-anterior/`](trabalho-anterior/) é a primeira entrega: manifests de
referência do nyx, o verificador original, o laboratório em kind e a revisão
do padrão com nove achados. É o fluxo de onde a skill nasceu (ver
[`origem.md`](origem.md)), e foi mantido como evidência. A CI
(`.github/workflows/manifests.yml`) continua rodando sobre ele e, agora,
também os testes do script da skill.
