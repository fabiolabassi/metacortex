## Causa

A tag `v1.14.2` não existe no registry de onde o deploy está puxando a imagem. Nenhum pod do `orion-web` consegue subir. Os 3 pods estão em `ImagePullBackOff`, e o kubelet registra o erro abaixo:

```
Failed to pull image "fabricioveronez/fake-shop:v1.14.2": rpc error: code = NotFound
... docker.io/fabricioveronez/fake-shop:v1.14.2: not found
```

O código é `NotFound`. O Docker Hub respondeu que essa referência não existe. Isso descarta falta de credencial (daria `unauthorized`), limite de requisições e problema de rede.

## O cluster não confirma o relato do chamado

O chamado diz que "o pod nunca foi substituído", como se a versão antiga continuasse rodando. Não é o que o cluster mostra:

- O Deployment `orion-web` está na **revision 1, generation 1**, criado às 23:36:01Z (hora UTC) de hoje.
- Existe **um único ReplicaSet** (`orion-web-67cd86ffd5`), que escalou de 0 para 3. Não há ReplicaSet de versão anterior.
- Condições: `MinimumReplicasUnavailable` e, desde 23:46:02Z, `ProgressDeadlineExceeded`.

Em `orion-stg`, então, não houve atualização de uma versão que funcionava. O Deployment foi criado do zero já com a tag que não existe, e nunca houve pod saudável para substituir. Ou o namespace foi recriado, ou o "estava funcionando" se refere a outro ambiente. Isso precisa ser confirmado com o cliente.

## Hipótese mais provável (não verificada)

O Deployment aponta para `docker.io/fabricioveronez/fake-shop`, a imagem pública. Pelo padrão da Metacortex, o Loom espelha as imagens para o registry interno, algo como `registry.metacortex.io/orion/fake-shop:<tag>`. Se o release do Loom anunciou a `v1.14.2`, ela provavelmente foi publicada **no registry interno**, e o manifesto aplicado ainda referencia a origem pública, onde essa tag nunca existiu. Outra possibilidade é diferença no nome da tag, como `1.14.2` sem o `v`. Eu só tenho acesso ao cluster, então não consultei nenhum dos dois registries.

## Próximos passos sugeridos

1. Conferir no release do Loom qual é a **referência completa** publicada (registry, repositório e tag) e se ela existe de fato.
2. Corrigir o `image` do Deployment para essa referência e reaplicar. Os pods vão sair do backoff sozinhos.
3. Lateral, mas vale registrar: o `DB_PASSWORD` está em texto puro no manifesto, inclusive na anotação `last-applied-configuration`. O padrão pede `secretKeyRef`.

O `orion-postgres` está saudável (1/1 Running) e não tem relação com o problema. Não alterei nada no cluster.