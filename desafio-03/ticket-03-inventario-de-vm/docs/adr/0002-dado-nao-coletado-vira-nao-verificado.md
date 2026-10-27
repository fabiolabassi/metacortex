# ADR-0002: Dado não coletado vira `nao_verificado` na regra, sem abortar

- Status: aceito
- Data: 2026-10-26

## Contexto

Parte dos dados exige privilégio: a configuração efetiva do `sshd` e as
chaves autorizadas de outras contas. A coleta, em geral, entra com usuário
comum. Um comando também pode não existir (host mínimo sem `ss`) ou devolver
algo que não dá para interpretar. O enunciado diz que reportar como conforme
é falso e que abortar não ajuda.

## Decisão

1. Cada comando remoto devolve o próprio código de saída (`rc`). `rc != 0`,
   seção ausente ou saída que o parser não entende ⇒ o campo do inventário
   fica `null` e a falha é anotada com um motivo.
2. Uma regra cujo dado é `null` sai `nao_verificado`, com `motivo`. As outras
   regras seguem normalmente.
3. **Valor vazio legítimo não é falha**: `/proc/swaps` só com cabeçalho é
   "sem swap" (`false`); `authorized_keys` inexistente é "zero chaves".
4. **Evidência parcial pode condenar, mas não absolver**: uma chave estranha na
   conta lida já é `desvio`; "todas as chaves são da plataforma" só é
   `conforme` se todas as contas foram lidas.
5. `--sudo` tenta `sudo -n` só nos dados privilegiados. Se o `sudo` pedir
   senha ou for negado, o dado fica `null`, e não há erro.
6. Código de saída 2 para "sem desvio, mas incompleto", diferente de 0.

## Alternativas descartadas

| Alternativa | Ganha | Perde |
|---|---|---|
| **Abortar a execução** no primeiro dado faltante | simples | um `sshd -T` sem root derruba a auditoria das outras 10 regras; o Roster fica sem nada |
| **Tratar como conforme** ("não achei problema") | relatório "limpo" | mentira: o enunciado proíbe, e a Segurança perde a única informação que importa |
| **Tratar como desvio** | conservador | infla a contagem de desvios com falta de privilégio; mistura "host errado" com "auditoria incompleta" |
| **Exigir root sempre** | todas as regras fecham | obriga sudo sem senha em todo o parque só para auditar; aumenta a superfície |

## Consequências

- (+) O pipeline distingue três estados pelo código de saída: 0, 1 e 2.
- (+) A falta de privilégio fica visível e acionável (rodar com `--sudo`).
- (−) O parser precisa diferenciar "vazio" de "falhou" seção a seção, com teste para cada uma.
