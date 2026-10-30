# coleta-remota Specification

## Purpose
Conectar a uma VM por SSH com as credenciais do operador e coletar o estado
real do host sem alterar nada nele, falhando de forma explicável quando o host
não pode ser alcançado.

## Requirements

### Requirement: Conexão com credenciais do operador
A ferramenta SHALL receber endereço, porta (padrão 22), usuário e caminho da chave privada, e SHALL autenticar no host usando somente essa chave, sem pedir nada interativamente.

#### Scenario: Chave aceita
- **WHEN** o operador executa `roster-audit --endereco 10.42.7.14 --usuario auditor --chave ~/.ssh/auditoria`
- **THEN** a ferramenta conecta, coleta e produz o relatório sem nenhuma pergunta no terminal

#### Scenario: Chave inexistente
- **WHEN** o caminho passado em `--chave` não existe ou não pode ser lido
- **THEN** a ferramenta termina com código 3 e mensagem de erro de uso, sem tentar conectar

### Requirement: Coleta só de leitura
A coleta MUST NOT instalar, criar, alterar ou apagar nada no host auditado. Nenhum arquivo SHALL ser copiado para o host, e todos os comandos executados no host SHALL ser comandos de leitura.

#### Scenario: Host intacto após a auditoria
- **WHEN** uma auditoria completa termina
- **THEN** nenhum arquivo do host foi criado ou modificado pela ferramenta, exceto os registros de login gerados pelo próprio servidor SSH

### Requirement: Dados coletados
A coleta SHALL obter, numa única sessão: endereço usado na conexão, hostname reportado pelo host, instante da coleta em UTC, distribuição e versão do SO, versão do kernel em execução, unidades systemd ativas com o tipo (`service` ou `socket`), estado e tamanho do swap, portas TCP em escuta com endereço de bind e processo dono, chaves SSH autorizadas com sua identificação, valor efetivo de login de root do `sshd` e estado e mecanismo de sincronização de tempo.

#### Scenario: Porta em escuta com bind
- **WHEN** o host tem `node_exporter` escutando em `0.0.0.0:9100`
- **THEN** o inventário contém `{"porta": 9100, "bind": "0.0.0.0", "processo": "node_exporter"}` quando o processo é visível ao usuário da coleta, e `"processo": null` quando não é

#### Scenario: Configuração efetiva do root login
- **WHEN** o arquivo `sshd_config` não menciona `PermitRootLogin` mas um arquivo em `sshd_config.d/` define `PermitRootLogin yes`
- **THEN** o valor coletado é o efetivo (`yes`), obtido de `sshd -T`, e não o texto de um arquivo isolado

### Requirement: Privilégio opcional sem interação
Com a opção `--sudo`, a ferramenta SHALL tentar obter os dados privilegiados com `sudo` não interativo. Se o `sudo` exigir senha ou for negado, a coleta MUST continuar, e o dado SHALL ficar como não coletado.

#### Scenario: Sudo pede senha
- **WHEN** o operador usa `--sudo` e o usuário da coleta não tem sudo sem senha
- **THEN** a auditoria termina normalmente e as regras que dependiam do dado privilegiado saem `nao_verificado`

### Requirement: Chave privada nunca exposta
Nem o conteúdo nem o caminho da chave privada SHALL aparecer na saída padrão, na saída de erro, em log ou em mensagem de erro, inclusive quando o `ssh` falha por causa da chave.

#### Scenario: Chave com permissão aberta
- **WHEN** a chave privada tem permissão 0644 e o `ssh` se recusa a usá-la
- **THEN** a mensagem diz que a chave tem permissão aberta demais, sem citar o caminho do arquivo

### Requirement: Host inalcançável explicado
Quando a conexão falha, a ferramenta SHALL terminar com código 4 e uma mensagem de uma linha que diga o que houve (endereço não resolvido, conexão recusada, tempo esgotado, chave recusada, chave do host divergente, conexão encerrada pelo host), sem stack trace e sem produzir relatório.

#### Scenario: Endereço errado
- **WHEN** o endereço não responde
- **THEN** a ferramenta escreve `roster-audit: erro: <endereco>:<porta> não respondeu em <N>s` no stderr, nada no stdout, e sai com código 4

#### Scenario: Chave recusada
- **WHEN** o host recusa a chave para o usuário
- **THEN** a mensagem diz que o host recusou a chave para o usuário informado e o código de saída é 4

#### Scenario: SSH fora do ar
- **WHEN** a porta SSH do host recusa conexão
- **THEN** a mensagem diz que o endereço recusou a conexão e o código de saída é 4

### Requirement: Verificação da chave do host
A ferramenta SHALL exigir que a chave do host já esteja no `known_hosts` do operador, a menos que `--aceitar-host-novo` seja passado, caso em que SHALL aceitar e registrar uma chave nova, mas MUST recusar uma chave divergente da registrada.

#### Scenario: Host novo sem a flag
- **WHEN** o host não está no `known_hosts` e `--aceitar-host-novo` não foi passado
- **THEN** a conexão é recusada com mensagem que cita `--aceitar-host-novo` e código 4
