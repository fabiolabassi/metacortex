# TRD: `roster-audit`

Requisitos de produto no [PRD](01-PRD.md). Decisões estruturais em ADR:

- [ADR-0001](adr/0001-ssh-do-sistema-e-coleta-numa-sessao.md): comunicação com o host;
- [ADR-0002](adr/0002-dado-nao-coletado-vira-nao-verificado.md): dado não coletado;
- [ADR-0003](adr/0003-python-com-biblioteca-padrao.md): linguagem.

## 1. Visão geral

```
estação do operador                                   VM auditada
┌────────────────────────────────────┐   ssh (1 sessão)  ┌──────────────────┐
│ cli ─► conexao ─► coleta (script) ─┼──── stdin ──────► │ /bin/sh -s       │
│                    ▲               │◄─── stdout ────── │ (só leitura)     │
│        parser ◄────┘               │   seções ##RA##   └──────────────────┘
│          │                          │
│          ▼                          │
│      inventario ─► conformidade ─► saida (json | markdown) ─► exit code
└────────────────────────────────────┘
```

Módulos (`src/roster_audit/`):

| Módulo | Responsabilidade |
|---|---|
| `cli.py` | argumentos, orquestração, código de saída, mensagens de erro |
| `conexao.py` | monta e roda o `ssh`, traduz falha de conexão em erro tipado |
| `coleta.sh` | script POSIX enviado por stdin; só comandos de leitura |
| `parser.py` | seções de texto → `inventario` (dict do formato JSON) |
| `regras.py` | `inventario` + baseline → lista de `conformidade` |
| `saida.py` | JSON e Markdown a partir do mesmo resultado |
| `baseline.py` | carga e validação do `baseline.yaml` |

## 2. Coleta (ADR-0001)

Uma só chamada:

```
ssh -o BatchMode=yes -o IdentitiesOnly=yes -o ConnectTimeout=10
    -o StrictHostKeyChecking=yes|accept-new -o LogLevel=ERROR
    -i <chave> -p <porta> <usuario>@<endereco> -- /bin/sh -s
```

O script vai por stdin. Nada é copiado para o host. Cada seção é delimitada
assim:

```
##RA## <nome> rc=<codigo de saida do comando>
<stdout do comando>
```

O stderr de cada comando é descartado no host (`2>/dev/null`). O código de
saída diz se o dado foi lido. Todos os comandos rodam com `LC_ALL=C`.

| Seção | Comando | Privilégio |
|---|---|---|
| `hostname` | `hostname` | não |
| `os_release` | `cat /etc/os-release` | não |
| `kernel` | `uname -r` | não |
| `units` | `systemctl list-units --type=service,socket --state=active --no-legend --plain --no-pager` | não |
| `swaps` | `cat /proc/swaps` | não |
| `listen` | `ss -H -t -l -n -p`; com `--sudo`, `sudo -n ss ...` e, se o sudo falhar, o `ss` comum | não para a porta; **sim** para o processo de outros usuários |
| `authkeys_self` | `cat ~/.ssh/authorized_keys` | não (só a própria conta) |
| `authkeys_all` | `sudo -n sh -c 'for f in /root/.ssh/authorized_keys /home/*/.ssh/authorized_keys; do …'` | **sim** (`--sudo`) |
| `sshd_t` | `sshd -T` sem sudo; com `--sudo`, `sudo -n sshd -T` | **sim** |
| `timedatectl` | `timedatectl show -p NTPSynchronized -p NTP` | não |

Timeout total da sessão: 60 s (`--timeout`).

## 3. Regras: o que cada uma compara

Cada linha produz exatamente uma entrada em `conformidade`, na ordem desta tabela.

| Regra | Encontrado | Conforme quando | `nao_verificado` quando |
|---|---|---|---|
| `so.distribuicao` | `ID` do os-release | `== ubuntu` | os-release ilegível |
| `so.versao_minima` | `VERSION` (ex.: `22.04.4`), senão `VERSION_ID` | versão ≥ mínima (comparação numérica por partes) | idem |
| `kernel.versao_minima` | `uname -r` | parte numérica ≥ mínima (`5.15.0-118-generic` → `5.15.0`) | `uname` falhou |
| `servicos.ativos` | lista dos esperados que **não** estão ativos | lista vazia. `x` está ativo se `x.service` **ou** `x.socket` está ativo | `systemctl` falhou |
| `servicos.proibidos` | lista dos proibidos que **estão** ativos | lista vazia (nome exato da unidade: `telnet.socket`) | `systemctl` falhou |
| `swap.habilitado` | `true (4G)` / `false` | igual ao esperado | `/proc/swaps` ilegível |
| `portas_em_escuta.publicas_permitidas` | portas com bind público que **não** estão na lista e **não** estão em `somente_rede_interna` | nenhuma | `ss` falhou |
| `portas_em_escuta.somente_rede_interna` | para cada porta da lista, os binds não internos | nenhum bind público ou wildcard nessas portas (porta ausente é conforme) | `ss` falhou |
| `chaves_ssh.emitidas_por` | chaves cujo comentário **não** termina em `@<emitidas_por>` | todas as chaves de todas as contas são da plataforma | só a própria conta foi lida e todas as chaves lidas são da plataforma |
| `ssh.login_de_root` | `permitrootlogin` efetivo | `no` ⇔ esperado `false`. `prohibit-password`, `without-password`, `forced-commands-only` e `yes` contam como **login permitido** | `sshd -T` não rodou |
| `ntp.sincronizado` | `NTPSynchronized` | igual ao esperado | `timedatectl` falhou |

**Classes de bind** (para as duas regras de porta):
loopback (`127.0.0.0/8`, `::1`) é ignorado; wildcard (`0.0.0.0`, `::`, `*`)
é público; RFC1918 e `fc00::/7` são internos; qualquer outro endereço é
público.

**Assimetria proposital da regra de chaves:** uma chave estranha na conta
lida já é desvio, e não precisa ler as outras contas para afirmar isso. Já
"conforme" exige ter lido todas.

**Mecanismo de NTP:** é o primeiro ativo entre `chrony`, `systemd-timesyncd`
e `ntp`/`ntpsec`, tirado da lista de unidades. Não entra no veredito.

## 4. Veredito, severidade e resumo

- `desvio` recebe `severidade` ∈ {`critico`, `alto`, `medio`}, lida do bloco
  `severidade` do baseline. Regra sem severidade no baseline é erro de baseline
  (código 3), não default silencioso.
- `nao_verificado` recebe `motivo` legível ("exige privilégio que o usuário da
  coleta não tem", "comando `ss` indisponível no host").
- `resumo` conta os três vereditos e os desvios por severidade.

## 5. Código de saída

| Código | Significado | Uso no pipeline |
|---|---|---|
| 0 | todas as regras `conforme` | ok |
| 1 | pelo menos um `desvio` | host fora do padrão |
| 2 | sem desvio, mas pelo menos um `nao_verificado` | auditoria incompleta, rodar com mais privilégio |
| 3 | erro de uso: argumento, baseline inválido, chave inexistente ou ilegível | corrigir a chamada |
| 4 | host inalcançável ou autenticação recusada | o host não foi auditado |

`1` vence `2`: um host com desvio e com regra não verificada sai com `1`.

## 6. Falhas de conexão (RF-07)

O `ssh` sai com 255 em erro de conexão. O stderr é classificado por padrão
de texto e **nunca é repassado cru**, porque pode conter o caminho da chave
(`Load key "...": bad permissions`).

| Padrão no stderr | Mensagem |
|---|---|
| `Could not resolve hostname` | não foi possível resolver o endereço `<endereco>` |
| `Connection refused` | `<endereco>:<porta>` recusou a conexão; o SSH está fora do ar ou a porta está errada |
| `timed out`, `No route to host`, `Network is unreachable` | `<endereco>:<porta>` não respondeu em N s |
| `Permission denied` | o host recusou a chave para o usuário `<usuario>` |
| `Host key verification failed`, `REMOTE HOST IDENTIFICATION HAS CHANGED` | a chave do host não confere com o known_hosts; use `--aceitar-host-novo` só se o host for novo |
| `bad permissions`, `UNPROTECTED PRIVATE KEY` | a chave privada tem permissão aberta demais (precisa ser 600) |
| `Connection closed`, `kex_exchange_identification` | a conexão foi encerrada pelo host antes da autenticação |
| outro | falha de SSH não classificada (código 255) |

Formato da mensagem no stderr: `roster-audit: erro: <mensagem>`. Nada vai
para o stdout, para não ser confundido com relatório. Sem stack trace: o
`main` captura `RosterAuditError` e as exceções inesperadas, e estas últimas
saem com mensagem genérica e código 4.

## 7. Segurança

- A chave é passada ao `ssh` por `-i`. A ferramenta nunca a abre, só confere
  que ela existe e é legível. O caminho não aparece na saída nem nas mensagens.
- `--verbose` mostra as seções coletadas e os códigos de retorno, nunca a
  linha de comando do `ssh`.
- Host key estrita por padrão.
- O script remoto é estático (`coleta.sh`, empacotado). Nenhum argumento do
  usuário é interpolado nele, então não há como injetar comando no host.

## 8. Testes

| Nível | O que cobre |
|---|---|
| unidade | parser com saídas reais capturadas das VMs de teste (`tests/fixtures/`), regras com inventários sintéticos (conforme, desvio, privilégio ausente), comparação de versões, classes de bind |
| erro | classificação de cada padrão de stderr; a mensagem não contém o caminho da chave |
| integração | contra VMs QEMU reais (Ubuntu 24.04 conforme e Ubuntu 22.04 com desvios), evidências em `evidencias/` |
