# Curadoria: onde a spec mudou e o que o agente entendeu diferente

Arco seguido: [brainstorm](00-brainstorm.md) → [PRD](01-PRD.md) →
[TRD](02-TRD.md) + [ADRs](adr/) → OpenSpec (proposta, specs, design,
tarefas) → implementação → validação nas VMs → arquivamento.

Agente: Claude Code 2.1.311 com Claude Opus 5.5. O mesmo agente escreveu os
documentos e o código. Por isso "o que o agente entendeu diferente" aparece
aqui como o que o **código** fez diferente do que o **documento** dizia,
pego por teste ou por execução real.

## 1. Onde a spec precisou ser corrigida durante a implementação

| # | O que o documento dizia | O que a execução mostrou | Correção |
|---|---|---|---|
| 1 | TRD §2: `listen` com `ss -H -t -l -n -p`, sem privilégio. A spec `coleta-remota` promete o processo dono "quando o processo é visível ao usuário da coleta" | o teste com a **saída real** da VM conforme falhou: mesmo com `--sudo`, `processo` vinha `null` em todas as portas. Com `--sudo`, o processo **é** visível ao usuário, mas o `ss` rodava sem `sudo` | `coleta.sh` passou a usar `sudo -n ss` com `--sudo`, e o `ss` comum se o `sudo` falhar (as portas continuam verificáveis). TRD §2 atualizado |
| 2 | TRD §3: a regra das chaves é `nao_verificado` quando só a própria conta foi lida | correta, mas a mensagem gerada era "todas as 1 chaves dela são da plataforma" | concordância por número no motivo |
| 3 | spec `relatorio`: Markdown com `true (4G)` para swap | a VM com 512 MB de swap saiu `true (512.0M)`: o `/proc/swaps` desconta uma página (524284 KiB) | arredondamento para inteiro quando a diferença é menor que 5% de uma unidade |
| 4 | TRD §6 previa "host key divergente" só como padrão de texto | na prática, apareceu ao **recriar** a VM de teste: o `known_hosts` guardava a chave da VM anterior | a mensagem distingue "host desconhecido" de "chave **mudou**", que pode ser interceptação. Os dois casos estão em `evidencias/03-host-inalcancavel/` |
| 5 | brainstorm e TRD: `ssh` ativo por `ssh.service` **ou** `ssh.socket` (Ubuntu 24.04) | na 24.04 do laboratório, `ssh.socket` **e** `ssh.service` estavam ativos (o login ativa o serviço); na 22.04, só `ssh.service`. A regra continua necessária para um host 24.04 sem sessão aberta, e foi coberta por teste sintético | nenhuma; mantida e testada |
| 6 | spec `conformidade`: 9100 em `0.0.0.0` | o `ss` mostrou `*:9100` para o node_exporter em `0.0.0.0` (socket IPv6 dual-stack) e `*:23` para o telnet | `*` já estava na classe "pública"; o caso real confirmou a decisão |

## 2. O que o agente entendeu diferente do que estava escrito

- **A primeira versão do teste de determinismo não provava nada.** As duas
  execuções caíram no mesmo segundo, e `coletado_em` saiu igual nas duas. Um
  JSON idêntico, nesse caso, não mostra que só `coletado_em` muda. O script de
  evidências passou a esperar 5 s entre as execuções. Agora o arquivo
  `determinismo.txt` mostra os dois instantes diferentes e o resto idêntico.
- **"Chave privada não aparece na saída"** foi lido pelo agente, de início,
  como "o conteúdo da chave". A spec foi escrita mais estrita: nem o **caminho**
  aparece, porque o `ssh` repassa o caminho em `Load key "...": bad permissions`.
  O código não repassa o stderr do `ssh` em caso nenhum, e o teste
  `test_classificacao` confere a ausência do caminho.
- **`argparse` sai com 2 em argumento inválido**, e 2 significa "auditoria
  incompleta" no contrato do TRD. O agente, de início, deixou o padrão. Um
  pipeline leria "faltou `--usuario`" como "host auditado com regra não
  verificada". Corrigido com `error()` sobrescrito para sair com 3, e testado.
- **O exemplo do enunciado mostra `ssh.login_de_root: null` como
  `nao_verificado`, e o agente pensou primeiro em ler `/etc/ssh/sshd_config`
  como fallback.** O enunciado pede a configuração **efetiva**. O arquivo pode
  ser sobrescrito por `sshd_config.d/` (é exatamente o que a VM de desvios faz,
  com `10-legado.conf`). O fallback foi descartado: sem `sshd -T`, a regra fica
  `nao_verificado`.

## 3. Saídas ruins registradas

- Um comando de geração de evidência mal escrito (expansão de variável do zsh)
  travou e precisou ser interrompido. Virou o script `lab/evidencias.sh`, em
  bash, reproduzível.
- O download da imagem 22.04 "falhou" com código 1 porque o comando terminava
  em `command -v cloud-localds` (ausente). A imagem estava íntegra (sha256 OK).
  O laboratório usa `genisoimage`.
- Ao recriar a VM conforme, o `known_hosts` do operador ficou com a chave da
  VM anterior. A entrada foi removida com `ssh-keygen -R "[127.0.0.1]:2221"`
  depois de capturar a evidência. Num uso real, o laboratório deveria ter um
  `known_hosts` próprio (`--known-hosts`, anotado como evolução).

## 4. O que fica para a v2

- `--known-hosts` para não misturar laboratório com o `known_hosts` do operador.
- Portas UDP com critério explícito (ignorar cliente DHCP e resolvedor local).
- Validar chaves por CA SSH em vez de comentário.
- Vários hosts por execução, com saída JSON Lines para o Roster.
