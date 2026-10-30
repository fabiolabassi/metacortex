# ADR-0002: Cliente oficial do Kubernetes para Python

- Status: aceito
- Data: 2026-10-27

## Contexto

O dashboard precisa:

- ler o contexto corrente do kubeconfig;
- autenticar com o que o kubeconfig trouxer: certificado de cliente (o
  `platform`/`platform-ro` do exemplo), token, ou `exec` plugin (EKS, GKE, OIDC);
- listar seis tipos de recurso;
- distinguir 401, 403 e cluster inacessível.

## Decisão

Usar o pacote `kubernetes` (cliente oficial, fixado em **37.0.1**, de
2026-10-09). `config.load_kube_config()` uma vez na subida, `CoreV1Api`,
`AppsV1Api` e `DiscoveryV1Api` só com `list_*`, e `_request_timeout` curto.

## Alternativas consideradas

| Alternativa | Autenticação e contexto | Tipagem e campos ausentes | Erros | Custo |
|---|---|---|---|---|
| **Cliente oficial** (escolhida) | resolve kubeconfig, contexto corrente, certificados, token e `exec` plugin, como o kubectl | modelos tipados; campo ausente vira `None` explícito, sem `KeyError` | `ApiException` com `.status` (401/403) e exceções de conexão do urllib3 separadas | ~1 dependência direta (+ urllib3, pyyaml etc.); versões acompanham a do Kubernetes |
| **`kubectl` como subprocesso** (`kubectl get ... -o json`) | herda tudo do kubectl, inclusive plugins | JSON cru (dict), campo ausente vira `KeyError` se não houver cuidado | só código de saída e texto no stderr; distinguir 401 de 403 de timeout é parsear mensagem | um processo por listagem (5 por atualização); depende do kubectl instalado e da versão; latência de ~100–300 ms por chamada só de fork/exec |
| **HTTP direto no apiserver** (`requests`/`urllib`) | reimplementar leitura do kubeconfig, contexto, CA, certificado de cliente, token e **exec plugin** (o pedaço mais complexo e mais sujeito a erro de segurança) | JSON cru | status HTTP direto (o melhor dos três) | mínimo em dependência, máximo em código próprio de autenticação, que é exatamente o que não se quer escrever numa ferramenta com acesso a produção |

## Consequências

- (+) O kubeconfig do exemplo do enunciado (certificado por usuário, `platform-ro`) funciona sem código próprio.
- (+) Os modelos tipados deixam explícito o "campo ausente = None" que o enunciado aponta.
- (+) A superfície de chamadas fica num módulo só (`leitura.py`), e o teste de "só leitura" verifica os nomes dos métodos.
- (−) O cliente Python fica algumas versões atrás do apiserver. Para `list` de recursos estáveis (v1, apps/v1, discovery/v1) isso não pesa.
- (−) O `load_kube_config` lê o arquivo uma vez. Trocar de contexto por fora exige reiniciar o dashboard, o que é exatamente o escopo pedido.
