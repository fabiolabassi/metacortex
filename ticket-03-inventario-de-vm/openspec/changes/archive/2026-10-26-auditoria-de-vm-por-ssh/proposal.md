## Why

O Roster é mantido à mão, e ninguém consegue dizer quantas VMs do parque
estão fora do padrão. Falta uma coleta reproduzível do estado real de cada
host. Contexto completo em `docs/00-brainstorm.md` e `docs/01-PRD.md`.

## What Changes

- Nova CLI `roster-audit` que audita **uma** VM por SSH, a partir da estação do operador, sem agente no host.
- Coleta só de leitura, numa sessão SSH: identificação, SO, kernel, unidades
  ativas, swap, portas TCP em escuta, chaves autorizadas, login de root
  efetivo e NTP.
- Comparação com `baseline.yaml`: uma entrada por regra, com veredito
  `conforme`, `desvio` (com severidade) ou `nao_verificado` (com motivo).
- Saída em JSON (Roster) e Markdown (plantão), gerada do mesmo dado.
- Códigos de saída distintos para conforme, desvio, incompleto, erro de uso e host inalcançável.
- `--sudo` opcional (`sudo -n`) para os dados que exigem privilégio.

## Capabilities

### New Capabilities
- `coleta-remota`: conexão SSH, coleta só de leitura, proteção da chave privada e classificação de falhas de conexão.
- `conformidade`: avaliação de cada regra do baseline contra o inventário coletado, com os três vereditos.
- `relatorio`: formatos JSON e Markdown e o contrato de código de saída.

### Modified Capabilities
<!-- nenhuma: projeto novo -->

## Impact

- Código novo em `src/roster_audit/` e testes em `tests/`.
- Dependências: Python ≥ 3.10, PyYAML e o cliente OpenSSH da estação.
- Decisões em `docs/02-TRD.md` e `docs/adr/0001..0003`.
- Nenhum sistema existente muda. O Roster passa a poder consumir o JSON.
