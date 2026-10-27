# ADR-0003: Python 3 com biblioteca padrão (+ PyYAML)

- Status: aceito
- Data: 2026-10-26

## Contexto

Quem mantém é o time de infraestrutura. A ferramenta precisa:

- montar JSON;
- comparar versões;
- classificar endereços IP;
- ler YAML;
- ser instalada sem atrito na estação do operador e no runner do pipeline do Roster.

## Decisão

Python ≥ 3.10, só biblioteca padrão (`subprocess`, `json`, `ipaddress`,
`argparse`, `datetime`) e PyYAML para o baseline. Instalação com `pip install .`
(entry point `roster-audit`) ou `python3 -m roster_audit`.

## Alternativas descartadas

| Alternativa | Ganha | Perde |
|---|---|---|
| **Bash + jq** | o time já escreve; nada a instalar além de jq | montar o JSON do enunciado e comparar versões em Bash é frágil; testes unitários penosos; tratamento de erro por `set -e` é armadilha conhecida |
| **Go** | binário único, sem runtime; tipagem | não há toolchain na estação; o time não mantém Go hoje; build e cross-compile no pipeline |
| **Python com paramiko/rich/pydantic** | API SSH, saída colorida, validação | três dependências nativas ou pesadas para ganhar pouco; ver ADR-0001 sobre SSH |

## Consequências

- (+) `ipaddress` resolve as classes de bind sem regex; `json` garante o formato.
- (+) Testes com `unittest`, sem framework extra.
- (−) Depende do Python da estação (≥ 3.10). Ubuntu 22.04+ já traz.
