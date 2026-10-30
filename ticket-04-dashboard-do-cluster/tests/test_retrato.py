"""Regras de exibicao com os modelos do cliente oficial, incluindo campos
ausentes (RNF-05), e classificacao de falhas de ambiente."""
import datetime
import io
import json
import threading
import unittest
import urllib.request
from unittest import mock

import urllib3
from kubernetes import client as k
from kubernetes.client.exceptions import ApiException

from retrato import retrato
from retrato.leitura import Cluster, FalhaDeLeitura
from retrato.servidor import servidor

AGORA = datetime.datetime.now(datetime.timezone.utc)


def meta(nome, **kw):
    return k.V1ObjectMeta(name=nome, creation_timestamp=AGORA, **kw)


def container(nome="api", probe=True):
    return k.V1Container(name=nome, image="x:1",
                         readiness_probe=k.V1Probe(http_get=k.V1HTTPGetAction(path="/r", port=80)) if probe else None)


class TestPod(unittest.TestCase):
    def test_crashloop_com_oom(self):
        cs = k.V1ContainerStatus(
            name="api", image="x", image_id="", ready=False, restart_count=17,
            state=k.V1ContainerState(waiting=k.V1ContainerStateWaiting(
                reason="CrashLoopBackOff", message="back-off 5m0s restarting failed container")),
            last_state=k.V1ContainerState(terminated=k.V1ContainerStateTerminated(
                reason="OOMKilled", exit_code=137)))
        p = k.V1Pod(metadata=meta("nyx-api-6b7c9d4f8-4kq2m"), spec=k.V1PodSpec(containers=[container()]),
                    status=k.V1PodStatus(phase="Running", container_statuses=[cs]))
        l = retrato.linha_pod(p)
        self.assertEqual((l["estado"], l["ultimo_termino"], l["reinicios"], l["prontos"]),
                         ("CrashLoopBackOff", "OOMKilled (137)", 17, "0/1"))
        self.assertTrue(l["falha"])

    def test_pending_sem_container_statuses(self):
        p = k.V1Pod(metadata=meta("p"), spec=k.V1PodSpec(containers=[container(), container("b")]),
                    status=k.V1PodStatus(phase="Pending", conditions=[k.V1PodCondition(
                        type="PodScheduled", status="False", reason="Unschedulable",
                        message="0/1 nodes are available")]))
        l = retrato.linha_pod(p)
        self.assertEqual((l["estado"], l["prontos"], l["reinicios"]), ("Unschedulable", "0/2", 0))

    def test_marca_sem_readiness(self):
        p = k.V1Pod(metadata=meta("p"), spec=k.V1PodSpec(containers=[container(probe=False)]),
                    status=k.V1PodStatus(phase="Running"))
        self.assertTrue(retrato.linha_pod(p)["sem_readiness"])


class TestDeployment(unittest.TestCase):
    def test_ready_replicas_ausente_e_zero(self):
        d = k.V1Deployment(
            metadata=meta("orion-web"),
            spec=k.V1DeploymentSpec(replicas=3, selector=k.V1LabelSelector(),
                                    template=k.V1PodTemplateSpec(spec=k.V1PodSpec(containers=[container()]))),
            status=k.V1DeploymentStatus(replicas=3, unavailable_replicas=3, conditions=[
                k.V1DeploymentCondition(type="Available", status="False", reason="MinimumReplicasUnavailable")]))
        l = retrato.linha_deployment(d)
        self.assertEqual((l["prontas"], l["desejadas"], l["condicao"]), (0, 3, "MinimumReplicasUnavailable"))
        self.assertTrue(l["falha"])


def service(nome, seletor):
    return k.V1Service(metadata=meta(nome), spec=k.V1ServiceSpec(
        type="ClusterIP", selector=seletor, ports=[k.V1ServicePort(port=80, target_port=8080)]))


def fatia(svc, enderecos, com_porta=True):
    return k.V1EndpointSlice(address_type="IPv4", metadata=k.V1ObjectMeta(
        name=svc + "-x", labels={"kubernetes.io/service-name": svc}),
        endpoints=enderecos, ports=[k.DiscoveryV1EndpointPort(port=8080)] if com_porta else None)


def pod_com(rotulos):
    return k.V1Pod(metadata=k.V1ObjectMeta(name="p", labels=rotulos))


class TestService(unittest.TestCase):
    def test_slice_sem_endpoints_e_seletor_que_nao_casa(self):
        l = retrato.linha_service(service("nyx-api", {"app": "nyx-api"}),
                                  [fatia("nyx-api", None)], [pod_com({"app": "nyxapi"})])
        self.assertEqual(l["endpoint"], "sem endpoint")
        self.assertIn("nenhum pod do namespace casa com o seletor app=nyx-api", l["dica"])

    def test_ips_listados_nenhum_pronto(self):
        nao = k.V1EndpointConditions(ready=False)
        l = retrato.linha_service(service("nyx-api", {"app": "nyx-api"}), [fatia("nyx-api", [
            k.V1Endpoint(addresses=["10.0.0.1"], conditions=nao),
            k.V1Endpoint(addresses=["10.0.0.2"], conditions=nao)])], [])
        self.assertEqual((l["endpoint"], l["falha"]), ("0/2 prontos", True))

    def test_ready_nulo_conta_como_pronto(self):
        l = retrato.linha_service(service("s", {"a": "b"}), [fatia("s", [
            k.V1Endpoint(addresses=["10.0.0.1"], conditions=k.V1EndpointConditions(ready=None))])], [])
        self.assertEqual(l["endpoint"], "1/1 prontos")

    def test_porta_nao_resolvida(self):
        l = retrato.linha_service(service("s", {"a": "b"}), [fatia("s", [
            k.V1Endpoint(addresses=["10.0.0.1"])], com_porta=False)], [])
        self.assertEqual(l["endpoint"], "porta não resolvida")

    def test_sem_permissao_em_slices(self):
        l = retrato.linha_service(service("s", {"a": "b"}), [], [],
                                  {"tipo": "sem_permissao", "mensagem": "x"})
        self.assertEqual(l["endpoint"], "sem permissão")


class ClusterFalso:
    """Cada lista_* devolve itens ou lanca a falha configurada."""

    def __init__(self, **falhas):
        self.falhas = falhas

    def __getattr__(self, nome):
        recurso = nome.replace("lista_", "")

        def f(ns):
            if recurso in self.falhas:
                raise self.falhas[recurso]
            return []
        return f


class TestMontagem(unittest.TestCase):
    def test_secoes_independentes(self):
        negado = FalhaDeLeitura("sem_permissao", "Sem permissão para listar events em x.")
        r = retrato.monta(ClusterFalso(eventos=negado), "x")
        self.assertEqual(r["eventos"]["erro"]["tipo"], "sem_permissao")
        for s in ("pods", "deployments", "services"):
            self.assertEqual(r[s], {"itens": []})

    def test_excecao_inesperada_vira_erro_da_secao(self):
        r = retrato.monta(ClusterFalso(pods=ZeroDivisionError()), "x")
        self.assertEqual(r["pods"]["erro"]["tipo"], "interno")
        self.assertEqual(r["deployments"], {"itens": []})


class TestClassificacao(unittest.TestCase):
    def setUp(self):
        self.c = Cluster.__new__(Cluster)
        self.c.erro, self.c.servidor, self.c.contexto = None, "https://x:6443", "lattice-prod"

    def falha(self, exc):
        def chama(*a, **kw):
            raise exc
        with self.assertRaises(FalhaDeLeitura) as cm:
            self.c._chama("events", "nyx-prod", chama)
        return cm.exception

    def test_401(self):
        self.assertEqual(self.falha(ApiException(status=401)).tipo, "credencial")

    def test_403(self):
        f = self.falha(ApiException(status=403))
        self.assertEqual((f.tipo, f.mensagem), ("sem_permissao", "Sem permissão para listar events em nyx-prod."))

    def test_inacessivel(self):
        exc = urllib3.exceptions.MaxRetryError(None, "/", reason="Connection refused")
        self.assertEqual(self.falha(exc).tipo, "cluster_inacessivel")


class TestServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c = Cluster.__new__(Cluster)
        c.erro, c.contexto, c.cluster, c.servidor, c.usuario, c.namespace_padrao = (
            None, "ctx", "cl", "https://x", "u", "default")
        cls.srv = servidor(c, 0, 10)
        cls.porta = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def pede(self, metodo, caminho):
        req = urllib.request.Request("http://127.0.0.1:{}{}".format(self.porta, caminho), method=metodo,
                                     data=b"{}" if metodo != "GET" else None)
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read())

    def test_escuta_so_em_loopback(self):
        self.assertEqual(self.srv.server_address[0], "127.0.0.1")

    def test_metodos_de_escrita_sao_405(self):
        for m in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(m):
                status, corpo = self.pede(m, "/api/retrato/nyx-prod")
                self.assertEqual((status, corpo["erro"]["tipo"]), (405, "somente_leitura"))

    def test_contexto(self):
        status, corpo = self.pede("GET", "/api/contexto")
        self.assertEqual((status, corpo["contexto"]), (200, "ctx"))

    def test_namespace_invalido(self):
        self.assertEqual(self.pede("GET", "/api/retrato/..%2Fetc")[0], 400)


if __name__ == "__main__":
    unittest.main()
