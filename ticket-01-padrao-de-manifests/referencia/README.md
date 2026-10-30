# Implementação de referência

Este diretório guarda a solução manual que antecedeu a skill do Ticket 01:
manifests do cliente Nyx, o verificador inicial e os testes/fixtures desse
verificador. A skill final está em [`../skill/padrao-de-manifests/`](../skill/padrao-de-manifests/);
as execuções que comprovam seus modos de escrita e conferência estão em
[`../execucoes/`](../execucoes/).

| Caminho | Conteúdo |
|---|---|
| `manifests/nyx-prod/` | API, worker e CronJob de produção |
| `manifests/nyx-dev/` | API de desenvolvimento |
| `scripts/check_padrao.py` | Verificador usado na solução inicial |
| `tests/` e `exemplos/reprovados/` | Testes e fixtures do verificador inicial |
| `.trivy/` e `.trivyignore.yaml` | Configuração da varredura Trivy |

Para validar essa referência localmente, com Python 3 e PyYAML:

```bash
bash scripts/validate.sh
```

O workflow [`manifests.yml`](../../.github/workflows/manifests.yml) também
valida os manifests e roda a admissão no kind. A validação da skill é feita
separadamente pelo mesmo workflow.
