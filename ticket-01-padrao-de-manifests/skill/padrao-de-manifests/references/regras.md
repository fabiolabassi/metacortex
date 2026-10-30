# Regras do padrão (revisão 2026-07-29), com as armadilhas conhecidas

Obrigatória = a revisão barra. Recomendada = exceção justificada no PR.
Proibida = sem exceção para workload de cliente. Coluna "quem": `trivy`,
`script` (confere.py) ou `você` (exige ler o projeto).

## Bloco 1: Identidade

| # | Regra | Nível | Quem | Armadilha |
|---|---|---|---|---|
| 1.1 | nome em kebab-case, ≤ 63 | obrig. | script | Mais restritiva que a API de propósito (ConfigMap aceita ponto; a casa não). |
| 1.2 | namespace `<cliente>-<dev\|stg\|prod>` | obrig. | script | Objeto sem `namespace:` cai no namespace do contexto de quem aplica. |
| 1.3 | `app.kubernetes.io/{name,instance,part-of,managed-by}` em todo objeto | obrig. | script | Vale também no template do pod e no `jobTemplate`. `instance` = namespace; `part-of` = cliente. `app:` sozinho não atende. |
| 1.4 | seletor casa com os rótulos do pod | obrig. | script | No Deployment o apiserver já recusa. O silencioso é o **Service** (sobe sem endpoint), o `targetPort` nomeado que o container não declara e o PDB que não seleciona nada. `matchLabels` é imutável: use só `name` + `instance`, nunca `managed-by`. |
| 1.5 | anotações `metacortex.io/owner` e `/runbook` | rec. | script (aviso) | |
| 1.6 | container com nome do componente | rec. | script (aviso) | `app`, `main`, `container` são genéricos. |

## Bloco 2: Resiliência

| # | Regra | Nível | Quem | Armadilha |
|---|---|---|---|---|
| 2.1 | requests e limits de CPU e memória | obrig. | trivy (LOW!) + você (valores) | Trivy classifica como LOW; pipeline com corte em MEDIUM deixa passar. Limite de memória = 1,5x–2x o consumo em regime. |
| 2.2 | readiness e liveness, em endpoints que existem | obrig. | script (presença) + você (endpoints) | Liveness não checa banco. Job/CronJob: readiness não tem efeito; peça liveness + `activeDeadlineSeconds`. App lenta para subir: `startupProbe`. |
| 2.3 | `replicas >= 2` em prod | obrig. | script | Duas réplicas no mesmo nó não sobrevivem a drain: `topologySpreadConstraints` por hostname. |
| 2.4 | RollingUpdate `maxUnavailable: 0`, `maxSurge: 1` em prod | obrig. | script | `maxSurge: 1` precisa de folga na ResourceQuota. |
| 2.5 | PDB `minAvailable >= 1` em prod com >1 réplica | rec. | script (aviso) | `minAvailable` ≥ réplicas trava o drain. |
| 2.6 | `terminationGracePeriodSeconds` compatível | rec. | você | A app trata SIGTERM? |

## Bloco 3: Segurança

| # | Regra | Nível | Quem | Armadilha |
|---|---|---|---|---|
| 3.1 | sem `:latest` (nem imagem sem tag) | proib. | trivy (KSV-0013) + você (tag existe?) | |
| 3.2 | `runAsNonRoot`, `runAsUser: 10001`, `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `drop: [ALL]` | obrig. | trivy + você (onde grava, UID) | Três campos só existem no **container**; no `spec.securityContext` do pod o apiserver recusa o manifesto. Inclua `seccompProfile: RuntimeDefault` no pod: o texto da 3.2 não pede, mas Pod Security `restricted` recusa sem ele. A recusa aparece nos eventos do ReplicaSet, não do Deployment. |
| 3.3 | segredo nunca em texto (env, ConfigMap, comentário, Secret versionado) | proib. | script + você (quais vars são credencial) | O Trivy não pega `env.value` com senha nem URL com credencial. |
| 3.4 | `automountServiceAccountToken: false` | obrig. | script | KSV-0036 só dispara com `true` explícito; ausente passa no Trivy e monta o token. Declare no Pod e na SA. |
| 3.5 | ServiceAccount dedicada, RBAC mínimo | rec. | script (aviso) | |
| 3.6 | sem `hostNetwork`/`hostPID`/`privileged` | proib. | trivy (KSV-0008/09/10/17) | |
| 3.7 | imagem só de `registry.metacortex.io` | obrig. | trivy (KSV-0125 com `assets/trivy-data`) + script (imagem sem domínio) | KSV-0125 ignora imagem sem domínio (`nginx:1.27`). Imagem pública entra pelo Loom. |

## Fora do padrão, mas cobrado pelo cluster

- Pod Security `restricted`: `seccompProfile` (ver 3.2).
- `Endpoints` está descontinuado (v1.33+). Com `targetPort` errado o
  EndpointSlice mostra IPs com porta `<unset>`; endereço presente não basta.
