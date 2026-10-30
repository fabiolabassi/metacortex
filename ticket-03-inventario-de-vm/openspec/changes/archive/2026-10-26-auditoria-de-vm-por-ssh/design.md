## Context

Projeto novo, sem código anterior. Motivação em `proposal.md`, requisitos em
`specs/`. As três decisões estruturais estão em ADRs fora do OpenSpec e são
só referenciadas aqui:

- `docs/adr/0001`: OpenSSH do sistema, uma sessão, script por stdin;
- `docs/adr/0002`: dado não coletado vira `nao_verificado`;
- `docs/adr/0003`: Python com biblioteca padrão e PyYAML.

O detalhamento de comandos, regras e códigos está em `docs/02-TRD.md`.

## Goals / Non-Goals

**Goals:**
- Pipeline linear `coleta → parser → regras → saída`, com cada etapa testável sem SSH.
- Separar "falhou" de "vazio" em cada seção coletada.
- Mensagens de erro próprias, sem repassar texto do `ssh`.

**Non-Goals:**
- Plugin de regra customizada: o conjunto de regras é fixo na v1 e espelha o baseline.
- Execução paralela em vários hosts.

## Decisions

1. **Protocolo de seções no stdout** (`##RA## <nome> rc=<n>`). O parser não
   depende da ordem nem do número de linhas, e uma seção ausente vale como
   "falhou". Alternativa descartada: JSON montado no host com `printf`. Exige
   escapar strings em sh e quebra com caractere estranho no comentário de uma
   chave.
2. **O inventário é o próprio dict do JSON de saída.** O parser já produz o
   formato do enunciado, e as regras leem dele. Alternativa descartada:
   dataclasses intermediárias, que exigiriam uma conversão a mais sem ganho de
   tipagem relevante.
3. **Falhas de coleta ficam num dict paralelo** (`falhas[secao] = motivo`),
   fora do JSON. As regras consultam esse dict para preencher `motivo`.
   Alternativa descartada: pôr o motivo dentro do inventário, o que polui o
   formato que o Roster consome.
4. **Erro tipado**: `ErroDeUso` (código 3) e `HostInalcancavel` (código 4).
   Exceção inesperada vira mensagem genérica com código 4, sem traceback;
   `--debug` reativa o traceback para desenvolvimento.
5. **Baseline embutido** (`baseline_padrao.yaml` no pacote) igual ao do
   enunciado; `--baseline` sobrepõe.

## Risks / Trade-offs

- [Texto de erro do OpenSSH muda entre versões] → a tabela de padrões tem
  fallback "falha de SSH não classificada", que continua com código 4; teste
  por padrão.
- [`ss -p` sem root não mostra processo de outros usuários] → `processo: null`
  no inventário; o veredito de porta não depende do processo.
- [Ubuntu 24.04 ativa `ssh` por socket] → serviço esperado aceita `.service` ou `.socket`.
- [`sudo -n` registra tentativa no `auth.log` do host] → só com `--sudo` explícito; documentado.

## Migration Plan

Ferramenta nova. Instalação por `pip install .` ou execução direta com
`python3 -m roster_audit`. Rollback é não usar.
