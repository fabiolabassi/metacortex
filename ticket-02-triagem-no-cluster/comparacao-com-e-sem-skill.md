# Comparação: triagem com e sem skill

## Método

Comparação de dois casos do desafio, usando a segunda repetição em cada modo:
chamado 1 (OOMKilled) e chamado 3 (Service sem endpoints). O pedido, modelo e
MCP de leitura foram os mesmos. `Bash`, `Write` e `Edit` ficaram bloqueados.
Sem skill, as skills foram desativadas; com skill, ela não foi mencionada no
pedido.

As respostas completas estão em `execucoes/{sem-skill,com-skill}/chamado-N.r2.md`.
As métricas foram registradas nas trilhas correspondentes.

## Métricas

| Modo | Chamado | Tempo (s) | Turnos | Chamadas MCP | Fora do namespace | Tokens entrada | Tokens saída | Custo (US$) | Formato |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Sem skill | 1 | 28,6 | 9 | 7 | 0 | 77.240 | 2.213 | 0,139 | 0/4 |
| Sem skill | 3 | 24,1 | 8 | 6 | 1 | 65.380 | 1.867 | 0,088 | 1/4 |
| Com skill | 1 | 31,3 | 10 | 5 | 0 | 136.298 | 2.475 | 0,159 | 4/4 |
| Com skill | 3 | 27,0 | 12 | 7 | 0 | 193.059 | 2.473 | 0,178 | 4/4 |
| **Média sem skill** | | **26,4** | **8,5** | **6,5** | **0,5** | **71.310** | **2.040** | **0,114** | |
| **Média com skill** | | **29,2** | **11** | **6** | **0** | **164.679** | **2.474** | **0,168** | |

O formato conta quatro seções do método da skill: causa, contraprova,
conferência do relato e itens não verificados.

## Resultado

As quatro execuções identificaram a causa correta. A diferença observada foi
de consistência: a skill usou as quatro seções padronizadas nos dois casos;
sem ela, o chamado 1 não usou nenhuma e o chamado 3 usou uma. No chamado 3,
a execução sem skill consultou um recurso fora do namespace e atribuiu o 503
ao proxy sem verificar quem o devolvia. Com a skill, a consulta ficou no
namespace indicado e a causa não verificada foi explicitada.

Nos dois casos medidos, a skill aumentou o tempo médio em 11%, o custo em
48% e os tokens de entrada em 131%; as chamadas MCP médias foram semelhantes.
Essa amostra pequena não demonstra que a skill melhora a precisão da causa.
Ela mostra padronização da resposta e melhor delimitação de escopo, com custo
adicional.
