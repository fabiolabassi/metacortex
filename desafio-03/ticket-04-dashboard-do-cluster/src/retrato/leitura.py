"""UNICO modulo que fala com a API do Kubernetes (TRD §5).

So expoe leitura: toda chamada a API aqui e list_* ou read_*. O teste
tests/test_somente_leitura.py analisa o codigo e falha se aparecer outro
verbo ou se outro modulo importar `kubernetes`.
"""
import logging

import urllib3
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from kubernetes.config.config_exception import ConfigException

log = logging.getLogger("retrato")
TIMEOUT = (3, 8)  # (conexao, leitura) em segundos


class FalhaDeLeitura(Exception):
    def __init__(self, tipo, mensagem):
        super().__init__(mensagem)
        self.tipo, self.mensagem = tipo, mensagem

    def como_dict(self):
        return {"tipo": self.tipo, "mensagem": self.mensagem}


class Cluster:
    """Contexto corrente do kubeconfig, lido uma vez na subida (RF-01)."""

    def __init__(self, kubeconfig=None):
        self.erro = None
        self.contexto = self.cluster = self.servidor = self.usuario = None
        self.namespace_padrao = "default"
        try:
            _, atual = config.list_kube_config_contexts(config_file=kubeconfig)
            ctx = atual.get("context") or {}
            self.contexto = atual.get("name")
            self.cluster, self.usuario = ctx.get("cluster"), ctx.get("user")
            self.namespace_padrao = ctx.get("namespace") or "default"
            cfg = client.Configuration()
            config.load_kube_config(config_file=kubeconfig, client_configuration=cfg)
            cfg.retries = False  # falha rapida: quem tenta de novo e o ciclo de 10 s
            self.servidor = cfg.host
            api = client.ApiClient(cfg)
            self.core, self.apps, self.discovery = (
                client.CoreV1Api(api), client.AppsV1Api(api), client.DiscoveryV1Api(api))
        except (ConfigException, OSError, TypeError, KeyError) as e:
            self.erro = FalhaDeLeitura(
                "kubeconfig", "Não foi possível carregar o contexto corrente do kubeconfig: {}".format(
                    str(e).splitlines()[0][:200]))

    def info(self):
        return {"contexto": self.contexto, "cluster": self.cluster, "servidor": self.servidor,
                "usuario": self.usuario, "namespace_padrao": self.namespace_padrao,
                "erro": self.erro.como_dict() if self.erro else None}

    # --- leitura ----------------------------------------------------------------

    def _chama(self, recurso, ns, funcao, *args, **kwargs):
        if self.erro:
            raise self.erro
        try:
            return funcao(*args, _request_timeout=TIMEOUT, **kwargs).items
        except ApiException as e:
            raise self._classifica_api(e, recurso, ns)
        except (urllib3.exceptions.HTTPError, OSError) as e:
            log.info("cluster inacessivel ao listar %s: %s", recurso, type(e).__name__)
            raise FalhaDeLeitura(
                "cluster_inacessivel",
                "O cluster {} não respondeu (timeout de {} s ou conexão recusada).".format(
                    self.servidor, TIMEOUT[0]))

    def _classifica_api(self, e, recurso, ns):
        if e.status == 401:
            return FalhaDeLeitura(
                "credencial", "A credencial do contexto {} foi recusada pelo cluster (expirada ou "
                              "inválida). Renove o login e recarregue.".format(self.contexto))
        if e.status == 403:
            onde = " em {}".format(ns) if ns else ""
            return FalhaDeLeitura("sem_permissao",
                                  "Sem permissão para listar {}{}.".format(recurso, onde))
        if e.status == 404:
            return FalhaDeLeitura("nao_encontrado", "Namespace {} não existe.".format(ns))
        return FalhaDeLeitura("api", "O apiserver respondeu {} ao listar {}.".format(e.status, recurso))

    def lista_namespaces(self):
        return self._chama("namespaces", None, self.core.list_namespace)

    def lista_pods(self, ns):
        return self._chama("pods", ns, self.core.list_namespaced_pod, ns)

    def lista_deployments(self, ns):
        return self._chama("deployments", ns, self.apps.list_namespaced_deployment, ns)

    def lista_services(self, ns):
        return self._chama("services", ns, self.core.list_namespaced_service, ns)

    def lista_endpointslices(self, ns):
        return self._chama("endpointslices", ns, self.discovery.list_namespaced_endpoint_slice, ns)

    def lista_eventos(self, ns):
        return self._chama("events", ns, self.core.list_namespaced_event, ns)
