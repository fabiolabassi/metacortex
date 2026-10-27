## 1. Estrutura

- [x] 1.1 Criar o pacote `src/roster_audit/` com `__main__.py` e `pyproject.toml` (entry point `roster-audit`); verificar com `python3 -m roster_audit --help`
- [x] 1.2 Embutir `baseline_padrao.yaml` igual ao do enunciado e o carregador com validação (regra sem severidade = erro de baseline); verificar com teste de carga e de baseline inválido

## 2. Coleta remota

- [x] 2.1 Escrever `coleta.sh` (POSIX, só leitura, seções `##RA##` com `rc`) e verificar com `sh -n` e rodando localmente com `sh coleta.sh`
- [x] 2.2 Implementar `conexao.py` (ssh com BatchMode, IdentitiesOnly, ConnectTimeout, host key estrita, `--aceitar-host-novo`, `--sudo`) e verificar que a linha de comando não é impressa em nenhum modo
- [x] 2.3 Classificar falhas de conexão pela tabela do TRD §6 e verificar com teste por padrão, incluindo a ausência do caminho da chave na mensagem

## 3. Parser e regras

- [x] 3.1 Implementar `parser.py` (seções → inventário + falhas) e verificar com fixtures capturadas das VMs de teste
- [x] 3.2 Implementar as 11 regras em `regras.py` conforme a spec `conformidade` e verificar com testes de conforme, desvio e `nao_verificado` para cada uma
- [x] 3.3 Implementar comparação de versão e classes de bind e verificar com testes (`5.15.0-118-generic` < `6.5`, `22.04.4` ≥ `22.04`, `10.0.2.15` interno, `0.0.0.0` público, `127.0.0.53` ignorado)

## 4. Saída e CLI

- [x] 4.1 Implementar JSON e Markdown em `saida.py` a partir do mesmo resultado e verificar que as contagens batem entre os dois
- [x] 4.2 Implementar `cli.py` com códigos 0–4, erro sem traceback e `--debug`; verificar com testes de código de saída

## 5. Validação contra os critérios de pronto

- [x] 5.1 Subir VM Ubuntu 24.04 conforme (QEMU) e verificar CA-1: zero desvios com `--sudo`, código 0
- [x] 5.2 Rodar sem `--sudo` na VM conforme e verificar CA-3: `nao_verificado` separado de `conforme`, código 2
- [x] 5.3 Subir VM Ubuntu 22.04 com desvios e verificar CA-2: cada desvio com a severidade do baseline, código 1
- [x] 5.4 Verificar CA-4 com endereço errado, porta fechada e chave recusada: mensagem sem traceback, código 4, stdout vazio
- [x] 5.5 Verificar CA-5: duas execuções seguidas com JSON idêntico exceto `coletado_em`
- [x] 5.6 Verificar RNF-01: comparar lista de arquivos modificados no host antes e depois da auditoria
