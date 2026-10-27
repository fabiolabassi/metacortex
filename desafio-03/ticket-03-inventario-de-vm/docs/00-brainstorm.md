# Brainstorm: auditoria de VM por SSH (`roster-audit`)

Sessão de levantamento feita com o agente (Claude Code, Opus 5.5) antes de
qualquer documento formal. Formato: perguntas abertas, respostas e o que ficou
decidido, adiado ou descartado. Os itens marcados **→ ADR** viraram decisão
registrada.

## O problema, em uma frase

O Roster é mantido à mão e mente. Ninguém sabe quantas VMs estão fora do
padrão, porque não existe uma coleta reproduzível do estado real.

## Quem usa e quando

| Quem | Quando | O que precisa |
|---|---|---|
| Plantonista | no meio de um chamado, sobre **um** host | Markdown legível no terminal, em segundos |
| Pipeline do Roster | periodicamente, sobre o parque | JSON estável e código de saída que diga "conforme / desvio / não deu" |
| Segurança (Seraph) | auditoria | saber o que **não** foi verificado, separado do que está conforme |

## Perguntas e respostas

**1. Agente no host ou coleta remota?**
O enunciado fecha: sem agente. A coleta parte da máquina do operador por SSH.
Consequência: tudo que for coletado tem que existir em toda VM Ubuntu sem
instalar nada (`systemctl`, `ss`, `/proc`, `/etc/os-release`, `timedatectl`).

**2. Uma conexão por dado ou uma conexão para tudo?**
Uma conexão por dado é simples, mas lenta (são 9 grupos de dados) e
inconsistente: o estado pode mudar entre uma conexão e outra. Uma conexão só,
mandando um script por stdin e recebendo seções delimitadas, dá um retrato
único do host. **→ ADR-0001**.

**3. Biblioteca SSH ou o `ssh` do sistema?**
- **paramiko**: dependência a mais, e `known_hosts`, agente e `ProxyJump` para reimplementar.
- **Ansible**: grava arquivos temporários em `~/.ansible/tmp` no host. Viola o
  "nada é escrito no host".
- **OpenSSH do sistema**: já respeita `~/.ssh/config`, `known_hosts`, agente e
  bastion. O operador já usa.

**→ ADR-0001.**

**4. O que fazer quando um dado não sai?**
Três saídas possíveis: abortar, chutar "conforme" ou marcar "não verificado".
O enunciado descarta as duas primeiras. A pergunta real é **o que conta como
"não saiu"**. Comando inexistente, permissão negada e saída que não dá para
interpretar contam. Valor vazio legítimo (sem swap, sem chave) **não** conta.
**→ ADR-0002**.

**5. A ferramenta usa `sudo`?**
Sem `sudo`, duas regras quase nunca fecham com usuário comum: a configuração
efetiva do `sshd` (`sshd -T` precisa ler as chaves do host) e as chaves
autorizadas de outras contas. Decisão: `sudo -n` (nunca pede senha) só com a
flag `--sudo`. Sem a flag, essas regras saem `nao_verificado`, que é
exatamente o caso que o enunciado descreve. Com a flag, se o `sudo` pedir
senha, o resultado também é `nao_verificado`, sem travar.

**6. Linguagem?**
Quem mantém é infraestrutura. As candidatas são Bash, Python e Go.
- **Bash**: perde na hora de montar JSON e comparar versões.
- **Go**: entrega binário único, mas não há toolchain na estação e o time não escreve Go.
- **Python 3**: já está em toda estação, e só a biblioteca padrão mais PyYAML resolve.

**→ ADR-0003**.

**7. Como saber se uma chave foi "emitida pela plataforma"?**
O baseline diz `emitidas_por: metacortex-platform`, e o exemplo mostra
`platform@metacortex-platform`. Convenção adotada: o comentário da chave
termina em `@metacortex-platform`. Assinatura por CA SSH seria o certo, e fica
anotado como evolução. Hoje o parque não usa CA.

**8. Porta "pública" × "interna"?**
O bind decide, não o firewall. A ferramenta não enxerga regra de firewall
nem security group sem privilégio e sem API de nuvem. As classes são:

| Bind | Classe |
|---|---|
| `127.0.0.0/8`, `::1` | loopback (ignorado) |
| `0.0.0.0`, `::`, `*` | pública |
| RFC1918 e `fc00::/7` | interna |
| qualquer outro | pública |

**9. TCP e UDP?**
Só TCP em escuta na v1. Em UDP, "em escuta" é ambíguo: cliente DHCP e
resolvedor local aparecem como sockets UDP ligados, e marcariam desvio em host
sadio. Fica registrado como limite.

**10. Uma porta em `somente_rede_interna` também conta para `publicas_permitidas`?**
Não. Cada porta é julgada por **uma** regra só. Se não, 9100 em `0.0.0.0` vira
dois desvios críticos pelo mesmo fato.

**11. Código de saída.**
O pipeline precisa distinguir quatro situações: "conforme", "achei desvio",
"não consegui olhar tudo" e "nem cheguei no host". Mais o erro de uso. Cinco
códigos, documentados no TRD.

**12. Determinismo.**
Ordenar tudo que vem de listagem (serviços, portas, chaves) e nunca derivar
veredito de dado volátil (PID, uptime). Só o `coletado_em` muda entre duas
execuções.

## Fora do escopo (decidido aqui)

- Auditar **várias** VMs numa execução. Um host por chamada; paralelismo é do pipeline.
- Corrigir qualquer coisa no host.
- Escrever no Roster. A ferramenta emite JSON; quem publica é o pipeline.
- Firewall, regras de `iptables`/`nftables` e security groups.
- Validar a assinatura das chaves (CA SSH).
- Outras distribuições além de Ubuntu. O baseline só aceita Ubuntu; outra distro
  vira **desvio** de `so.distribuicao`, não erro.

## Riscos levantados

| Risco | Mitigação |
|---|---|
| Vazar a chave privada em mensagem de erro | nunca repassar o stderr do `ssh` cru; traduzir para mensagem própria; teste que procura o caminho e o conteúdo da chave na saída |
| Primeira conexão com host desconhecido (TOFU) | padrão estrito (`StrictHostKeyChecking=yes`); `--aceitar-host-novo` explícito para `accept-new` |
| Login SSH escreve em `wtmp`/`auth.log` | inerente a qualquer acesso remoto; documentado como a única escrita que acontece, e que não é da ferramenta |
| Ubuntu 24.04 ativa o `ssh` por socket | aceitar `ssh.service` **ou** `ssh.socket` ativo para o serviço `ssh` |
