# ADR-0001: Cliente OpenSSH do sistema, coleta numa sessão por stdin

- Status: aceito
- Data: 2026-10-26

## Contexto

A ferramenta roda na estação do operador e audita uma VM sem agente. Ela
precisa:

- autenticar com a chave que o operador passa;
- respeitar `known_hosts`, `~/.ssh/config` e um eventual bastion;
- coletar nove grupos de dados sem escrever nada no host.

## Decisão

Chamar o binário `ssh` do sistema por `subprocess`, **uma vez por auditoria**.
O script de coleta (`coleta.sh`, POSIX sh) vai por stdin para `/bin/sh -s`, e o
host devolve seções delimitadas (`##RA## <nome> rc=<n>`) no stdout.

Opções fixas: `BatchMode=yes` (nunca pergunta nada), `IdentitiesOnly=yes`,
`ConnectTimeout`, `LogLevel=ERROR` e `StrictHostKeyChecking=yes` por padrão
(`accept-new` com `--aceitar-host-novo`).

## Alternativas descartadas

| Alternativa | Ganha | Perde |
|---|---|---|
| **paramiko / asyncssh** | API Python, erro como exceção tipada | dependência nativa a mais; reimplementar `known_hosts`, agente, `ProxyJump` e `~/.ssh/config`; outra pilha criptográfica para auditar |
| **Ansible (fatos + `command`)** | módulos prontos, inventário | exige Python no host e **grava em `~/.ansible/tmp` no host**, o que viola o "nada é escrito"; pesado para um host |
| **Uma conexão `ssh` por dado** | parsing trivial | ~10 handshakes (lento); dados de instantes diferentes; mais registros de login no host |
| **Copiar o script com `scp` e executar** | script legível no host | escreve no host |

## Consequências

- (+) Zero dependência de SSH no Python. O operador usa a mesma configuração do dia a dia.
- (+) Retrato do host num instante só, com um registro de login por auditoria.
- (+) O script é estático e sem interpolação, então não há injeção de comando.
- (−) Erro de conexão vem como texto no stderr do `ssh`, e é preciso
  classificá-lo por padrão (TRD §6). Mudança de texto em versão futura do
  OpenSSH cai em "falha não classificada", que continua saindo com código 4.
- (−) Depende de `/bin/sh` no host. Toda VM Ubuntu tem.
