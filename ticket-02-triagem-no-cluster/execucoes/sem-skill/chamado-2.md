Fiz a triagem. A loja está fora do ar porque a imagem `fabricioveronez/fake-shop:v1.14.2` não existe no Docker Hub. Nenhum pod do `orion-web` consegue subir.

**O que o cluster mostra (`orion-stg`)**

- Deployment `orion-web`: 0/3 disponíveis, condição `MinimumReplicasUnavailable`.
- Os 3 pods (`orion-web-67cd86ffd5-*`) estão em `ImagePullBackOff`.
- O kubelet tentou baixar a imagem 5 vezes e recebeu sempre o mesmo erro:
  ```
  failed to resolve reference "docker.io/fabricioveronez/fake-shop:v1.14.2": ... not found
  ```
  O código é `NotFound`. Não é falta de credencial, limite de requisições nem problema de rede. O registry respondeu que essa referência não existe. Com esse tipo de resposta, o mais provável é que o repositório exista e a tag `v1.14.2` nunca tenha sido publicada (ou tenha outro nome, como `1.14.2` sem o `v`). Só tenho acesso ao cluster, então não consultei a lista de tags no Docker Hub.
- O `orion-postgres` está saudável (1/1 Running). O banco não tem relação com o problema.

**Correção do relato do chamado**

O chamado diz que "o pod nunca foi substituído", mas o cluster não mostra isso. Não houve rolling update parado com um pod antigo ainda no ar:

- O deployment está em `revision: 1` e foi criado às 20:36:01 de hoje.
- `OldReplicaSets: <none>`. Só existe um ReplicaSet, que subiu de 0 para 3.

Ou seja, o deployment foi criado do zero, ou apagado e recriado, já apontando para a tag que não existe. Em um rolling update normal, o RollingUpdate manteria os pods da versão anterior servindo tráfego enquanto os novos falhassem. Aqui não sobrou nenhuma versão antiga, e por isso a loja caiu por completo em vez de só ficar sem a versão nova. Vale perguntar ao time do Loom como o deploy foi aplicado (delete + apply, namespace recriado, etc.).

**Próximos passos sugeridos** (não alterei nada no cluster)

1. Confirmar com quem fez o release qual tag foi realmente publicada no Docker Hub. Pode ter havido falha no push ou divergência entre o nome anunciado e o publicado.
2. Para restaurar a loja já, apontar o deployment para a última tag conhecida que funciona. Não há revisão anterior para usar `kubectl rollout undo`.
3. Para evitar que se repita: validar no pipeline que a imagem existe (`docker manifest inspect` / `crane digest`) antes do apply, e não recriar o deployment a cada publicação.

**Achado à parte:** `DB_PASSWORD: Pg1234` está em texto puro no pod template. O certo seria passar para um `Secret`.