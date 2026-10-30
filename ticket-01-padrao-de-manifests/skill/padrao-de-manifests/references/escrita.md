# Modo escrita: decisões que o padrão não dita

O padrão diz *o que* o manifesto precisa ter. Estas são as decisões de *como*
que aparecem quando o projeto real não colabora. Registre cada uma na seção
**Decisões** da entrega.

## Levantamento do projeto (antes do YAML)

| Dado | Como achar |
|---|---|
| Porta | `listen(`, `--bind`, `app.run(port=`, `EXPOSE`, `CMD` da imagem |
| Endpoints de saúde | grep por `health`, `ready`, `live`, `ping`, `status`. Leia o handler: ele consulta o banco? |
| Variáveis lidas | `process.env.`, `os.getenv(`, `os.environ`, `Settings(BaseSettings)`, README |
| Credenciais | dessas variáveis, as que são senha, token, chave ou URL com usuário e senha |
| Onde grava | `/tmp`, cache, `PROMETHEUS_MULTIPROC_DIR`, uploads, sqlite, `__pycache__` |
| UID e comando | `docker image inspect <img> --format '{{.Config.User}} {{.Config.Cmd}} {{.Config.Entrypoint}}'` |
| Start | entrypoint/script: roda migração? semeia dados? |

Se o repositório não tem Dockerfile, a imagem publicada é a fonte da verdade
para UID, workdir e comando.

## Aplicação sem endpoint de saúde

Não invente rota. Escolha entre o que existe e diga o que cada probe garante:

- **readiness**: uma rota GET barata que dependa do que a app precisa para
  servir (ex.: a página inicial que lê do banco). Se falhar, o pod só sai do
  Service. Não reinicia.
- **liveness**: algo que **não** dependa do banco. Na ordem de preferência:
  rota que não toca dependência (ex.: `/metrics`); `tcpSocket` na porta (só
  prova que o processo aceita conexão); `exec` como último recurso.
- **startupProbe** quando a partida for lenta (migração, warm-up), para não
  afrouxar a liveness.
- Registre como dívida: a aplicação deveria expor `/health` e `/ready`.

## Migração de banco no start

Com `replicas >= 2`, cada réplica roda a migração ao subir, e as réplicas
concorrem entre si. Em prod, a 2.4 (`maxSurge: 1`) faz a réplica nova migrar
enquanto a antiga ainda serve o esquema anterior.

Opções, da preferida para a pior:

1. **Job de migração** separado, com a mesma imagem e o mesmo `securityContext`,
   rodando só o comando de migração. O Deployment sobrescreve `command`/`args`
   para subir só o servidor. A readiness que toca o banco segura o tráfego até
   o esquema existir. O Job é o primeiro arquivo aplicado; num pipeline vira
   hook pré-deploy (Argo CD `PreSync`, Helm `pre-upgrade`).
2. `initContainer` com a migração: ordena por pod, mas não entre pods. As
   réplicas ainda concorrem.
3. Manter no entrypoint: só aceitável com 1 réplica (dev).

Job também segue o padrão: 1.3, 2.1, 3.x, `backoffLimit`,
`activeDeadlineSeconds`, `ttlSecondsAfterFinished`. A 2.2 não se aplica (ver
`regras.md`).

## Senha que não pode ir para o manifesto

- O manifesto referencia: `valueFrom.secretKeyRef: {name: <cliente>-db, key: password}`.
- O Secret **não** é versionado. Documente o comando que o cria:
  ```bash
  kubectl -n <ns> create secret generic <cliente>-db \
    --from-literal=username=... --from-literal=password="$(pass show ...)"
  ```
- Se a aplicação tem **default de senha no código** (ex.:
  `os.getenv('DB_PASSWORD', 'Pg1234')`), avise: sem o Secret, ela sobe com a
  senha do código em vez de falhar. Use `optional: false` (o default) para o
  pod não subir sem o Secret.
- Se a app monta a URL do banco sozinha a partir de partes (`DB_HOST`,
  `DB_USER`...), não crie `DATABASE_URL`: a app não lê.
- Outros segredos no código (ex.: `app.secret_key = '...'` fixo) não se
  resolvem por manifesto. Reporte como achado para o time do cliente.

## readOnlyRootFilesystem

Monte `emptyDir` (com `sizeLimit`, e `medium: Memory` se for pequeno) em cada
caminho gravável. Se a imagem espera um **subdiretório** pronto (ex.:
`/tmp/metrics`), um `emptyDir` em `/tmp` o esconde. Monte o subdiretório
também, ou monte direto nele.

## Valores de recurso sem medição

Comece por requests modestos e limits de memória folgados, e diga que é chute
inicial a ajustar pela regra 1,5x–2x quando houver métrica. Referência para
começar: Node/Express ~ 128Mi/256Mi; Flask+gunicorn com 2–4 workers ~ 192Mi/384Mi.
