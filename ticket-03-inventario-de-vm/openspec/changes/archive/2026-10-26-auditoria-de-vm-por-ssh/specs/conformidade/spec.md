## Purpose

Comparar o inventário coletado com o baseline do parque e produzir, para cada
regra, um veredito verificável e reproduzível.

## ADDED Requirements

### Requirement: Uma entrada por regra
A avaliação SHALL produzir exatamente uma entrada por regra do baseline, na ordem: `so.distribuicao`, `so.versao_minima`, `kernel.versao_minima`, `servicos.ativos`, `servicos.proibidos`, `swap.habilitado`, `portas_em_escuta.publicas_permitidas`, `portas_em_escuta.somente_rede_interna`, `chaves_ssh.emitidas_por`, `ssh.login_de_root`, `ntp.sincronizado`. Cada entrada SHALL conter `regra`, `esperado`, `encontrado` e `veredito`.

#### Scenario: Contagem
- **WHEN** a auditoria termina com o baseline padrão
- **THEN** a lista `conformidade` tem 11 entradas e a soma do `resumo` é 11

### Requirement: Três vereditos
O veredito SHALL ser `conforme`, `desvio` ou `nao_verificado`. Um `desvio` SHALL trazer a `severidade` atribuída pelo baseline à regra. Um `nao_verificado` SHALL trazer `motivo` e MUST NOT ser contado como `conforme`.

#### Scenario: Severidade do baseline
- **WHEN** o host tem swap habilitado e o baseline lista `swap.habilitado` em `critico`
- **THEN** a entrada é `{"regra": "swap.habilitado", "veredito": "desvio", "severidade": "critico", ...}`

#### Scenario: Dado privilegiado ausente
- **WHEN** a coleta entra com usuário comum, sem `--sudo`, e `sshd -T` falha por falta de privilégio
- **THEN** `ssh.login_de_root` sai `nao_verificado` com `motivo` explicando o privilégio, `encontrado` é `null`, e as demais regras são avaliadas normalmente

### Requirement: Versões mínimas
As regras de versão SHALL comparar numericamente, parte por parte, a versão encontrada com a mínima do baseline, ignorando sufixos não numéricos.

#### Scenario: Kernel antigo
- **WHEN** o kernel é `5.15.0-118-generic` e o mínimo é `6.5`
- **THEN** `kernel.versao_minima` é `desvio` com severidade `medio`

#### Scenario: Versão de SO com ponto
- **WHEN** a versão do SO é `22.04.4` e a mínima é `22.04`
- **THEN** `so.versao_minima` é `conforme`

### Requirement: Serviços ativos e proibidos
Um serviço esperado SHALL ser considerado ativo se a unidade `<nome>.service` ou `<nome>.socket` estiver ativa. Uma unidade proibida SHALL ser comparada pelo nome completo da unidade, incluindo o tipo.

#### Scenario: Serviço esperado ausente
- **WHEN** `chrony` não tem unidade ativa
- **THEN** `servicos.ativos` é `desvio` (`alto`) e `encontrado` lista `chrony` entre os ausentes

#### Scenario: Socket proibido ativo
- **WHEN** `rpcbind.socket` está ativo
- **THEN** `servicos.proibidos` é `desvio` (`alto`) e `encontrado` lista `rpcbind.socket`

### Requirement: Portas por endereço de bind
O veredito de porta SHALL ser decidido pelo endereço de bind: loopback é ignorado; wildcard (`0.0.0.0`, `::`, `*`) e endereço não privado são públicos; RFC1918 e `fc00::/7` são internos. Uma porta listada em `somente_rede_interna` SHALL ser julgada apenas por essa regra.

#### Scenario: 9100 em todas as interfaces
- **WHEN** a porta 9100 está em `0.0.0.0`
- **THEN** `portas_em_escuta.somente_rede_interna` é `desvio` (`critico`) e `publicas_permitidas` não conta a 9100

#### Scenario: 9100 só no endereço interno
- **WHEN** a porta 9100 está apenas em `10.0.2.15`
- **THEN** `portas_em_escuta.somente_rede_interna` é `conforme`

#### Scenario: Porta pública não permitida
- **WHEN** a porta 111 está em `0.0.0.0`
- **THEN** `portas_em_escuta.publicas_permitidas` é `desvio` (`critico`) e `encontrado` lista a 111

### Requirement: Chaves emitidas pela plataforma
Uma chave SHALL ser considerada emitida pela plataforma quando seu comentário termina em `@<emitidas_por>`. Uma chave estranha em qualquer conta lida SHALL tornar a regra `desvio`. A regra SHALL ser `conforme` somente se as chaves de todas as contas foram lidas e todas são da plataforma; caso contrário, SHALL ser `nao_verificado`.

#### Scenario: Chave esquecida
- **WHEN** a conta da coleta tem uma chave `dozer@notebook`
- **THEN** `chaves_ssh.emitidas_por` é `desvio` (`critico`), mesmo sem ler as outras contas

#### Scenario: Só a própria conta lida
- **WHEN** sem `--sudo`, todas as chaves da própria conta são da plataforma
- **THEN** a regra é `nao_verificado`, com motivo dizendo que as outras contas não foram lidas

### Requirement: Login de root
`ssh.login_de_root` esperado `false` SHALL ser `conforme` somente quando o valor efetivo de `permitrootlogin` for `no`. Qualquer outro valor (`yes`, `prohibit-password`, `without-password`, `forced-commands-only`) SHALL ser tratado como login de root permitido.

#### Scenario: Padrão do Ubuntu
- **WHEN** o valor efetivo é `prohibit-password`
- **THEN** a regra é `desvio` (`alto`) com `encontrado` igual a `true (prohibit-password)`

### Requirement: Determinismo
Duas avaliações do mesmo host sem mudança de estado SHALL produzir o mesmo veredito em todas as regras e as mesmas listas na mesma ordem.

#### Scenario: Execução repetida
- **WHEN** a ferramenta roda duas vezes seguidas contra o mesmo host
- **THEN** o JSON das duas execuções difere apenas em `host.coletado_em`
