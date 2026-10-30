## Purpose

Entregar o resultado da auditoria em dois formatos derivados do mesmo dado,
JSON para o Roster e Markdown para o plantão, com código de saída utilizável
em pipeline.

## ADDED Requirements

### Requirement: JSON para o Roster
Com `--formato json`, a ferramenta SHALL escrever no stdout um único objeto JSON com as chaves `host`, `inventario`, `conformidade` e `resumo`, no formato definido no enunciado (`host.endereco`, `host.hostname`, `host.coletado_em` em ISO 8601 UTC com `Z`; `resumo` com `conforme`, `desvio`, `nao_verificado` e `por_severidade`).

#### Scenario: JSON válido
- **WHEN** o operador executa com `--formato json`
- **THEN** o stdout é um JSON válido que um `json.loads` lê sem erro e contém as quatro chaves de topo

### Requirement: Markdown para o plantão
Com `--formato markdown` (padrão), a ferramenta SHALL escrever um relatório com título `# Inventário de <hostname> (<endereco>)`, linha com instante e versão do baseline, e as seções `## Desvios` (tabela severidade, regra, esperado, encontrado, ordenada de crítico a médio), `## Não verificado` (tabela regra, motivo) e `## Conforme` (regras separadas por ` · `). Seção vazia SHALL ser omitida.

#### Scenario: Host com desvios e regra não verificada
- **WHEN** há desvios e uma regra não verificada
- **THEN** o Markdown traz a tabela de desvios ordenada por severidade e a tabela de não verificados separada da linha de conformes

### Requirement: Mesmo dado nos dois formatos
O Markdown e o JSON SHALL ser derivados do mesmo resultado de avaliação, de forma que as contagens e vereditos sejam idênticos entre os dois.

#### Scenario: Contagens iguais
- **WHEN** a mesma coleta é renderizada nos dois formatos
- **THEN** o número de linhas de desvio no Markdown é igual a `resumo.desvio` do JSON

### Requirement: Código de saída
A ferramenta SHALL sair com 0 quando todas as regras são `conforme`; 1 quando há ao menos um `desvio`; 2 quando não há desvio mas há ao menos um `nao_verificado`; 3 em erro de uso (argumento, baseline ou chave inválidos); 4 quando o host não pôde ser alcançado ou a autenticação falhou.

#### Scenario: Host conforme
- **WHEN** todas as 11 regras são `conforme`
- **THEN** o código de saída é 0

#### Scenario: Host inalcançável não é conforme
- **WHEN** o host não responde
- **THEN** o código de saída é 4 e nada é escrito no stdout
