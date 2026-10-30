A triagem terminou: a causa está confirmada. Usei só leituras pelo MCP, sem nenhuma alteração no cluster.

**Causa:** a imagem `fabricioveronez/fake-shop:v1.14.2` não existe no registry. O kubelet recebe `NotFound` ao baixá-la, e os 3 pods do `orion-web` ficam presos em `ImagePullBackOff`.

**Camada:** Imagem

**Evidências** (fonte → o que mostrou):
- `get deployments -n orion-stg` → `orion-web` está em **0/3**, com `UP-TO-DATE 3` e `AVAILABLE 0`. A imagem é `fabricioveronez/fake-shop:v1.14.2`.
- `get pods -n orion-stg` → os 3 pods `orion-web-67cd86ffd5-*` estão em `ImagePullBackOff` e nunca rodaram (0 restarts).
- `get events -n orion-stg` → o kubelet repete a mesma mensagem nos 3 pods: `failed to resolve reference "docker.io/fabricioveronez/fake-shop:v1.14.2": ... not found`. É `NotFound`, não `unauthorized` nem timeout. A tag (ou o repositório) não existe, e não é problema de credencial nem de rede.
- `describe deployment orion-web` → está na revisão **1**, com `OldReplicaSets: <none>`. O único ReplicaSet é `orion-web-67cd86ffd5`, criado do zero ("from 0 to 3").

**Contraprova:** o `orion-postgres`, no mesmo namespace e no mesmo nó, baixou `postgres:16-alpine` sem erro e está 1/1 Running. Então o nó, a rede e o acesso ao Docker Hub funcionam. O que falha é só a referência `v1.14.2`.

**O relato bate com o cluster?** Só em parte.
- A falha é mesmo no deploy da tag nova.
- Mas não houve substituição de pod que travou. O Deployment `orion-web` tem cerca de 7 minutos, a mesma idade do `orion-postgres`, está na revisão 1 e não tem ReplicaSet antigo. Ele foi recriado do zero, então nenhuma versão anterior estava servindo, e por isso a loja caiu por completo.
- Também não existe versão anterior para um `rollout undo` dentro do cluster. Vale perguntar ao time do Loom por que o namespace ou o Deployment foi recriado em vez de atualizado.

**Correção sugerida (não aplicada):** primeiro, confirmar com o time do Loom qual é a tag que foi publicada de verdade. A tag `v1.14.2` foi anunciada no release, mas não chegou a ser enviada ao registry (ou foi publicada com outro nome). Depois há duas saídas:
- enviar a imagem `v1.14.2` ao registry; ou
- corrigir o `image:` no manifesto do `orion-web` para uma tag que exista.

No pipeline, vale adicionar uma verificação de que a tag existe no registry antes do apply.

**Não verificado:**
- Quais tags existem de fato em `fabricioveronez/fake-shop`. Isso exige consultar o registry, que está fora do cluster.
- Quem recriou o Deployment, e por quê. O cluster não guarda o histórico anterior.

Achados paralelos, que não explicam o chamado:
- `DB_PASSWORD` está em texto puro no env do Deployment.
- A imagem vem do `docker.io` público, e não do registry interno.