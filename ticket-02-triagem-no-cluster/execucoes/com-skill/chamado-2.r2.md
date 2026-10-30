A triagem terminou. Fiz só leitura do namespace `orion-stg`, sem alterar nada no cluster.

**Causa:** a imagem `fabricioveronez/fake-shop:v1.14.2` não existe no Docker Hub. O registry respondeu `not found`, então os 3 pods do `orion-web` ficam em `ImagePullBackOff` e nenhum chega a iniciar.

**Camada:** Imagem

**Evidências** (fonte → o que mostrou):
- `kubectl_get deployments` → `orion-web` está `0/3`, com `UP-TO-DATE 3`, imagem `fabricioveronez/fake-shop:v1.14.2`.
- `kubectl_describe deployment orion-web` → `Progressing=False / ProgressDeadlineExceeded`, `Available=False`, **revisão 1** e `OldReplicaSets: <none>`.
- `kubectl_get pods` → os 3 pods `orion-web-67cd86ffd5-*` estão em `ImagePullBackOff`, com 0 restarts.
- `kubectl_describe pod orion-web-67cd86ffd5-4969z` → o kubelet registrou: `code = NotFound ... docker.io/fabricioveronez/fake-shop:v1.14.2: not found`. Foram 5 tentativas de pull e 42 back-offs. A mensagem é `NotFound`, então não é problema de credencial (`unauthorized`) nem de rede (timeout).

**Contraprova:** o `orion-postgres`, no mesmo nó, baixou `postgres:16-alpine` do mesmo Docker Hub e está `1/1 Running`. O nó tem acesso ao registry e não precisa de credencial para imagens públicas. O problema está só na tag do fake-shop.

**O relato bate com o cluster?** Não exatamente. Nada indica que houve uma substituição:
- O Deployment está na revisão 1 e não tem ReplicaSet antigo.
- Os dois Deployments do namespace têm a mesma idade, 14 minutos.

O `orion-web` foi criado do zero com a tag nova, e não havia pod da versão anterior para continuar servindo. Por isso a loja ficou fora do ar, em vez de ficar travada na versão antiga. Também não existe revisão anterior para usar com `rollout undo`.

**Correção sugerida (não aplicada):**
1. Confirmar com o time do Loom a tag que foi de fato publicada. A tag `v1.14.2` foi anunciada no release, mas não chegou ao registry. Pode ser falha no push do pipeline ou erro de digitação no anúncio.
2. Publicar a imagem com essa tag, ou corrigir o `image:` no manifesto do `orion-web` para uma tag que exista, e reaplicar pelo fluxo normal.

**Não verificado:**
- Quais tags do `fake-shop` existem no Docker Hub. As ferramentas da triagem só leem o cluster, não o registry.
- Se houve antes um deploy em outro objeto ou namespace. O cluster não dá nenhum indício disso.

Achados paralelos, não investigados:
- `DB_PASSWORD` está em texto puro no Deployment.
- A imagem vem do Docker Hub e não do registry interno.
- Não há requests/limits (o pod é `BestEffort`) nem probes.