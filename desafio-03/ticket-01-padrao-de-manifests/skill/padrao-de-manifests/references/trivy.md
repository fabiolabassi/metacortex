# O que o Trivy (v0.74.0) já cobre

Levantado rodando `trivy config` no manifesto barrado do nyx e em manifests de
teste com `hostNetwork`, `privileged`, imagem sem tag e imagem de outro
registry. `confere.py` usa esta tabela para traduzir KSV → regra.

| KSV | Sev. | Regra | O que pega |
|---|---|---|---|
| 0011, 0015, 0016, 0018 | LOW | 2.1 | falta requests/limits de CPU e memória |
| 0013 | MEDIUM | 3.1 | `:latest` **e** imagem sem tag |
| 0001 | MEDIUM | 3.2 | `allowPrivilegeEscalation` |
| 0003, 0004, 0106 | LOW | 3.2 | `capabilities.drop: [ALL]` |
| 0012 | MEDIUM | 3.2 | `runAsNonRoot` |
| 0014 | HIGH | 3.2 | `readOnlyRootFilesystem` |
| 0020, 0021 | LOW | 3.2 | `runAsUser`/`runAsGroup` > 10000 |
| 0030, 0104 | LOW/MED | 3.2 | `seccompProfile` |
| 0118 | HIGH | 3.2 | securityContext padrão |
| 0109 | HIGH | 3.3 | chave tipo senha em ConfigMap (só esse caso) |
| 0036 | MEDIUM | 3.4 | **só** `automountServiceAccountToken: true` explícito |
| 0008, 0009, 0010, 0017 | HIGH | 3.6 | hostIPC, hostNetwork, hostPID, privileged |
| 0125 | MEDIUM | 3.7 | registry fora da lista, **só** se a imagem tem domínio |

## Configuração usada

- `--severity LOW,MEDIUM,HIGH,CRITICAL`: sem LOW, 2.1 e partes da 3.2 somem.
- `--config-data assets/trivy-data`: define `registry.metacortex.io` como único
  registry confiável para a KSV-0125. Sem isso, toda imagem do parque é
  marcada como não confiável, porque a lista padrão é ACR/ECR/GCR.
- `--ignorefile assets/trivyignore.yaml`: ignora só a KSV-01010 (falso positivo:
  `HTTP_PORT: "8080"` em ConfigMap casa com o padrão de "passaporte").

## O que o Trivy não cobre e ficou no script

1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.2 (presença), 2.3, 2.4, 2.5, 3.3 (env/URL/
comentário/Secret no Git), 3.4 (campo ausente), 3.5, 3.7 (imagem sem domínio).
Nem `trivy fs --scanners secret` acha `postgres://nyx:s3nh4-do-banco@...`.
