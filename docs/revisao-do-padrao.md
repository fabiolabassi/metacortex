# Revisão do padrão — achados com evidência

Levantados ao escrever os manifests deste repositório e validá-los num cluster
real descartável (kind, **Kubernetes v1.36.1**, kubectl v1.36.1) e com
**Trivy 0.74.0**, em 2026-10-08. Todo achado tem reprodução: os de cluster em
[`lab/lab.sh`](../lab/lab.sh), os de varredura nos comandos citados. As saídas
abaixo foram copiadas da execução.

Nada aqui contesta o objetivo das regras. São pontos em que o texto do wiki,
seguido ao pé da letra, não entrega o que promete, ou em que a ferramenta que
o Bloco 3 cita não cobre o que parece cobrir.

| # | Achado | Gravidade | Regra |
| --- | --- | --- | --- |
| 1 | O exemplo da 3.2 é recusado pelo apiserver se for colocado no Pod | alta | 3.2 |
| 2 | Quem cumpre a 3.2 ao pé da letra é barrado pelo Pod Security | alta | 3.2 |
| 3 | A 1.4 descreve o sintoma no objeto errado; existem mais dois casos silenciosos | média | 1.4, 4.5 |
| 4 | O Pod Security barra o Pod, não o Deployment, e o motivo fica escondido | média | Bloco 3 |
| 5 | A 2.2 não serve para Job e CronJob | baixa | 2.2, 1.3 |
| 6 | A varredura do Trivy não cobre o que o Bloco 3 dá a entender | alta | 2.1, 3.2, 3.3, 3.7 |
| 7 | A 4.6 descreve uma API obsoleta, e o substituto engana | baixa | 4.6 |
| 8 | Falta mecanismo para registrar exceção com validade | média | Exceções |
| 9 | Pontos menores | — | 1.1, 1.3, 1.4, 2.4, 3.4 |

---

## 1. O exemplo da 3.2 é recusado se for colocado no Pod

O wiki mostra um bloco `securityContext` sem dizer onde ele entra. Três dos
cinco campos só existem no `SecurityContext` do **container**; o
`PodSecurityContext` não os tem. Quem copia o bloco para `spec.securityContext`,
o lugar mais intuitivo para uma regra que vale para o pod inteiro, recebe:

```
$ kubectl apply -f lab/21-securitycontext-do-wiki.yaml
Error from server (BadRequest): ... Pod in version "v1" cannot be handled as a Pod:
  strict decoding error: unknown field "spec.securityContext.allowPrivilegeEscalation",
  unknown field "spec.securityContext.capabilities",
  unknown field "spec.securityContext.readOnlyRootFilesystem"
```

**Proposta de texto:** separar em dois blocos.

```yaml
spec:
  securityContext:            # Pod
    runAsNonRoot: true
    runAsUser: 10001
    runAsGroup: 10001
    fsGroup: 10001
    seccompProfile: {type: RuntimeDefault}
  containers:
    - securityContext:        # cada container
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        privileged: false
        capabilities: {drop: ["ALL"]}
```

O verificador acusa o erro antes do PR (`exemplos/reprovados/05-securitycontext-no-pod.yaml`).

## 2. Quem cumpre a 3.2 ao pé da letra é barrado pelo Pod Security

Mesmo no nível certo, o bloco da 3.2 não inclui `seccompProfile`. Num namespace
com Pod Security `restricted`, que é a forma de o cluster impor o próprio
Bloco 3, o pod é recusado:

```
$ kubectl apply -f lab/21-securitycontext-do-wiki.yaml      # segundo objeto
Error from server (Forbidden): pods "lab-sc-nivel-container" is forbidden:
  violates PodSecurity "restricted:latest": seccompProfile (pod or container "api"
  must set securityContext.seccompProfile.type to "RuntimeDefault" or "Localhost")
```

**Proposta:** incluir `seccompProfile: {type: RuntimeDefault}` no bloco de Pod
da 3.2. Até lá, o verificador emite **AVISO** (não ERRO, porque a regra
escrita não pede o campo).

## 3. A 1.4 descreve o sintoma no objeto errado

O wiki diz que o seletor que não casa é "o mais silencioso: o objeto sobe, a
revisão passa, e o serviço simplesmente não tem para onde mandar tráfego". O
exemplo "errado" mostra `spec.selector` contra os rótulos do `template`, que é
a forma de um **Deployment**. Nesse caso o apiserver recusa na hora:

```
$ kubectl apply -f lab/22-seletor-deployment.yaml
The Deployment "lab-seletor-errado" is invalid: spec.template.metadata.labels:
  Invalid value: {"app":"nyxapi"}: `selector` does not match template `labels`
```

O caso silencioso de verdade é o **Service**. O laboratório encontrou mais dois
com o mesmo sintoma, que o wiki não cita:

| Objeto em `lab/10-api.yaml` | Aceito? | Endpoints | EndpointSlice | Tráfego |
| --- | --- | --- | --- | --- |
| `lab-api` (correto) | sim | 2 IPs, porta 8080 | 2 IPs, porta 8080 | `200 OK` |
| `lab-api-seletor-errado` (um hífen a menos) | sim | nenhum | nenhum | falhou |
| `lab-api-porta-errada` (`targetPort: web`, o container chama de `http`) | sim | **nenhum** | **2 IPs**, porta `<unset>` | falhou |
| `lab-pdb-sem-alvo` (PDB com o seletor errado) | sim | — | — | protege nada |

```
$ kubectl -n lab-dev get endpointslices
NAME                           ADDRESSTYPE   PORTS     ENDPOINTS                 AGE
lab-api-porta-errada-xwvms     IPv4          <unset>   10.244.0.10,10.244.0.13   39s
lab-api-r7dzj                  IPv4          8080      10.244.0.10,10.244.0.13   39s
lab-api-seletor-errado-8m8gx   IPv4          <unset>   <unset>                   39s

lab-api: 200 OK
lab-api-seletor-errado: falhou
lab-api-porta-errada: falhou
```

O `targetPort` nomeado errado é o mais traiçoeiro dos três: quem olha o
EndpointSlice vê os IPs dos pods e conclui que o Service está saudável.

**Proposta:** reescrever o exemplo da 1.4 com Service × Pod e citar
`targetPort` nomeado e PDB. Acrescentar uma nota dizendo que no Deployment o
erro é barrado na aplicação, o que é uma boa notícia. O verificador cobre os
três casos silenciosos (`exemplos/reprovados/02-service-sem-endpoint.yaml`).

## 4. O Pod Security barra o Pod, não o Deployment

Muda o que se procura no plantão. O Deployment sem `securityContext` é criado
com um `Warning`. A recusa acontece quando o ReplicaSet tenta criar o Pod, e o
sintoma é um Deployment parado em `0/1`:

```
$ kubectl apply -f lab/20-sem-securitycontext.yaml
Warning: would violate PodSecurity "restricted:latest": allowPrivilegeEscalation != false ...
deployment.apps/lab-sem-securitycontext created

deployment.apps/lab-sem-securitycontext   0/1     0            0
replicaset.apps/lab-sem-securitycontext-7d59c6c7b5   1   0   0

$ kubectl -n lab-dev get events --field-selector reason=FailedCreate
lab-sem-securitycontext-7d59c6c7b5   Error creating: pods "..." is forbidden: violates
  PodSecurity "restricted:latest": allowPrivilegeEscalation != false ...,
  unrestricted capabilities ..., runAsNonRoot != true ..., seccompProfile ...
```

Não existe Pod para descrever, e o Deployment não traz o motivo. A mensagem
está nos eventos do **ReplicaSet**. Por isso a CI deste repositório faz
`--dry-run=server` (que mostra o `Warning`) e o `validate.sh` também.

Como contraprova, os manifests de referência foram aplicados de verdade nos
namespaces `restricted`: todos os Pods foram **criados**, e param em
`ImagePullBackOff` só porque `registry.metacortex.io` não existe fora do parque.

## 5. A 2.2 não serve para Job e CronJob

A 1.3 cita Job e CronJob, e a 2.2 exige as duas probes "em qualquer ambiente".
Em carga batch a `readinessProbe` não tem efeito, porque nenhum Service manda
tráfego para um Job. O laboratório roda um Job com readiness e liveness. Ele
termina `Succeeded` com o container marcado como não pronto, e nada muda:

```
NOME                   FASE        READY
lab-job-probes-psjls   Succeeded   false
```

**Proposta:** limitar a 2.2 a workloads de longa duração (Deployment,
StatefulSet, DaemonSet). Para batch, pedir `livenessProbe` (pega o job
travado) e `activeDeadlineSeconds` (pega o job que nunca termina). O CronJob
deste repositório tem as duas probes para cumprir a regra como está escrita e
explica isso em comentário.

No mesmo CronJob aparece outra lacuna da 1.3: os rótulos precisam estar em
**três** níveis (CronJob, `jobTemplate.metadata` e `template.metadata`). Sem o
do meio, o Job criado de madrugada, que é o objeto que aparece no alerta,
nasce sem dono (`exemplos/reprovados/07-cronjob-rotulos.yaml`).

## 6. A varredura do Trivy não cobre o que o Bloco 3 dá a entender

O Bloco 3 diz que a varredura "não substitui esta página". Os números abaixo
mostram o tamanho dessa lacuna. Comandos:
`trivy config --config .trivy/trivy.yaml exemplos/reprovados/<arquivo>`.

**6a. A 3.7 gera achado no scan de Segurança.** Toda imagem do parque cai em
`KSV-0125 (MEDIUM) ... uses an image from an untrusted registry`. A regra lê
uma lista configurável, `data.ksv0125.trusted_registries`, que vem do código
da própria regra (`uses_untrusted_registry.rego`). Aqui ela é configurada em
[`.trivy/data/registries.yaml`](../.trivy/data/registries.yaml). **Não** foi
ignorada no `.trivyignore`, porque ignorar desligaria a checagem também para
imagens de fora.

**6b. Imagem sem domínio passa.** A mesma regra só avalia imagens com `/` e
domínio. `nginx:1.27`, que vem do Docker Hub implícito, não gera achado:

```
$ trivy config ... (01-wiki-errado.yaml com image: nginx:1.27) | grep -c KSV-0125
0
```

A 3.7 precisa de outro verificador. `scripts/check_padrao.py` faz isso.

**6c. Regras obrigatórias caem em LOW.** No `01-wiki-errado.yaml`, o Trivy
classifica como **LOW** a falta de `requests`/`limits` (KSV-0011/15/16/18,
regra 2.1), a falta de `capabilities.drop: ALL` (KSV-0003, 3.2) e
`runAsUser` ≤ 10000 (KSV-0020, 3.2). Um pipeline com corte em `MEDIUM`, o
comum, deixa passar regras **obrigatórias** do padrão. Este repositório roda
o Trivy com `LOW` incluso e passa limpo.

**6d. Segredo em texto puro não é detectado (3.3).** Nem o scan de
configuração nem o de segredos (`trivy fs --scanners secret`) marcam:
- `env.value: "postgres://nyx:s3nh4-do-banco@..."`, o exemplo "errado" do
  próprio wiki;
- `Secret` com `stringData` versionado no Git;
- credencial em comentário, que a 3.3 proíbe explicitamente.

O único caso pego é a chave `DB_PASSWORD` em ConfigMap (KSV-0109). O
verificador cobre os quatro (`exemplos/reprovados/03-segredos.yaml`).

**6e. Falso positivo em ConfigMap (KSV-01010).** `HTTP_PORT: "8080"` é marcado
como conteúdo sensível. Pelo código da regra (`configmap_with_sensitive.rego`),
o padrão de "passaporte" `^[A-Z0-9<]{3,20}$` casa com qualquer valor de 3 a 20
dígitos. Está no `.trivyignore.yaml` com o motivo e com escopo limitado a
`*/20-configmap.yaml`.

**Proposta para Segurança & Compliance:** publicar a configuração do Trivy do
pipeline (registries confiáveis e severidade mínima) junto com esta página, e
listar no Bloco 3 o que a varredura **não** cobre.

## 7. A 4.6 descreve uma API obsoleta

```
Warning: v1 Endpoints is deprecated in v1.33+; use discovery.k8s.io/v1 EndpointSlice
```

O que a 4.6 diz continua valendo: o Service sem pod não tem `subsets` na
resposta. Mas quem está chegando vai ver `EndpointSlice` nas ferramentas, e lá
o caso do achado 3 (`targetPort` errado) aparece **com** endereços.

**Proposta:** acrescentar um parágrafo sobre EndpointSlice e avisar que
"endereços presentes" não basta: a coluna `PORTS` precisa estar preenchida.

## 8. Falta mecanismo para registrar exceção com validade

A seção "Exceções" pede aprovação escrita "no PR, com prazo de validade". Na
prática o prazo vence e ninguém percebe, porque o PR já foi mergeado.

**Proposta, implementada aqui:** a exceção vai numa anotação do próprio objeto
e o verificador a aplica:

```yaml
metadata:
  annotations:
    excecao.metacortex.io/2.3: "validade=2026-12-31; aprovacao=<link do PR>"
```

- obrigatória + aprovação + dentro da validade → vira AVISO
- vencida, sem aprovação ou sem data → continua ERRO e o pipeline volta a
  barrar sozinho no dia seguinte ao vencimento
- proibida (3.1, 3.3, 3.6) → continua ERRO sempre

Testado em `exemplos/reprovados/06-excecoes.yaml` e `tests/` (inclusive o
último dia de validade).

## 9. Pontos menores

- **1.1** — "A API aceita menos do que as pessoas imaginam" vale para o
  Service, que recusa ponto (`"nyx.api": must not contain dots`). Não vale
  para o ConfigMap, que aceita `nyx.config`. Na v1.36 o Service também já
  aceita nome começando com dígito (`2fa-api` foi criado). A regra da casa
  continua certa; a justificativa pode dizer que é **mais restritiva que a
  API, de propósito**.
- **1.3** — vale exigir coerência: `instance` = namespace e `part-of` =
  cliente do namespace. Um `part-of` errado quebra em silêncio o rateio de
  custo que a própria regra cita. O verificador confere.
- **1.4** — dizer que `matchLabels` é imutável. Por isso o seletor deve usar
  só rótulos que não mudam (`name` e `instance`) e nunca `managed-by`, que muda
  no dia da migração para o Argo CD.
- **2.3 + 2.5** — duas réplicas no mesmo nó não sobrevivem a um drain, e o PDB
  não impede que sejam agendadas juntas. Recomendar
  `topologySpreadConstraints` por `kubernetes.io/hostname`. Avisar também que
  `minAvailable` ≥ réplicas trava o drain para sempre (o verificador avisa).
- **2.4** — `maxSurge: 1` precisa de folga na `ResourceQuota` do namespace.
  Sem ela, o pod extra é recusado por cota e o rollout para. É comportamento
  documentado do Kubernetes, mas não foi reproduzido neste laboratório.
- **3.4** — o campo existe no Pod e na ServiceAccount. Declarar nos dois cobre
  o Pod futuro que esquecer o campo.
