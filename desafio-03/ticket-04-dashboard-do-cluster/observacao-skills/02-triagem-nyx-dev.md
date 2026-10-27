Já tenho a causa: o pod não consegue baixar a imagem. Abaixo o resultado (só li o cluster, não alterei nada).

**Causa:** o nó não consegue resolver o nome do registry `registry.metacortex.io` no DNS. Por isso o pull da imagem `kube-news:v1` falha antes de chegar ao registry e o container nunca é criado.

**Camada:** Imagem

**Evidências** (fonte → o que mostrou):
- `get deployments -n nyx-dev` → `nyx-api` 0/1 com a imagem `registry.metacortex.io/nyx/kube-news:v1`. O `nyx-db` está 1/1.
- `describe deployment nyx-api` → `Available=False (MinimumReplicasUnavailable)`, revisão 1, sem `OldReplicaSets`. Foi uma criação do zero, então não há versão anterior para voltar.
- `get pods` → `nyx-api-c4f79c6bc-ttmkt` em `ErrImagePull`/`ImagePullBackOff`, com 0 restarts. O container nunca chegou a rodar.
- `describe pod` → evento do kubelet, repetido 5 vezes em cerca de 3 minutos:
  `dial tcp: lookup registry.metacortex.io on 172.23.0.1:53: no such host`
  Não é `not found`, que indicaria tag inexistente, nem `unauthorized`, que indicaria credencial. A falha é de DNS: o nó do kind (`kind-control-plane`) pergunta ao resolver da rede Docker (`172.23.0.1`) e esse resolver não conhece o host.

**Contraprova:** o `nyx-db` está no mesmo nó e usa `postgres:16-alpine`, que vem do Docker Hub, um nome que esse DNS resolve. O pull dele funcionou, então a rede do nó funciona. O problema está só no nome do registry interno.

**O relato bate com o cluster?** Sim. O deployment está 0/1 desde a criação, há cerca de 3 minutos.

**Correção sugerida (não aplicada):** o que fazer depende de onde a imagem deve vir:
- **Lab local com kind, sem acesso ao registry interno:** faça o build local e carregue a imagem no nó com o mesmo nome: `kind load docker-image registry.metacortex.io/nyx/kube-news:v1`. Como a tag é `v1` e não `latest`, o `imagePullPolicy` padrão é `IfNotPresent`, então o kubelet usa a imagem já carregada sem tentar o pull.
- **O registry existe e deveria estar acessível:** faça `registry.metacortex.io` resolver dentro do nó, com VPN, DNS da rede Docker ou um mirror/`hosts` configurado no containerd do kind via `containerdConfigPatches`.
- O manifesto em si não precisa mudar.

**Não verificado:**
- Se a imagem `nyx/kube-news:v1` existe de fato no registry. Não dá para saber, porque o pull nem chegou ao servidor. Mesmo depois de resolver o DNS, ainda podem aparecer `not found` ou `unauthorized`, e nenhum `imagePullSecrets` aparece na spec.
- O comportamento da aplicação depois de subir, incluindo ConfigMap, Secret e probes `/ready` e `/health`, porque o container nunca rodou.