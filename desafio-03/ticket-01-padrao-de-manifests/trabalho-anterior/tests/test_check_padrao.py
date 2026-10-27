"""Testes do verificador. Rodar com: python3 -m unittest -v"""
import datetime
import pathlib
import sys
import unittest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import check_padrao  # noqa: E402

REPROVADOS = sorted((RAIZ / "exemplos" / "reprovados").glob("*.yaml"))


def regras(achados, nivel):
    return {a[1] for a in achados if a[0] == nivel}


def espera(arquivo):
    """Le a primeira linha '# espera: 1.1 3.2 ...' do anti-padrao."""
    primeira = arquivo.read_text(encoding="utf-8").splitlines()[0]
    assert primeira.startswith("# espera:"), arquivo
    return set(primeira.split(":", 1)[1].split())


class ManifestsDeReferencia(unittest.TestCase):
    def test_sem_erro_e_sem_aviso(self):
        rel, n = check_padrao.verifica([RAIZ / "manifests"])
        self.assertGreater(n, 0)
        self.assertEqual(rel.achados, [], "\n".join(map(str, rel.achados)))


class AntiPadroes(unittest.TestCase):
    """Cada anti-padrao reprova exatamente nas regras que declara — nem mais,
    nem menos. 'Mais' indica falso positivo; 'menos', regra que regrediu."""

    def test_existem_anti_padroes(self):
        self.assertGreaterEqual(len(REPROVADOS), 5)

    def test_cada_um_reprova_no_que_declara(self):
        for arq in REPROVADOS:
            with self.subTest(arquivo=arq.name):
                rel, _ = check_padrao.verifica([arq])
                self.assertEqual(regras(rel.achados, "ERRO"), espera(arq))


class Excecoes(unittest.TestCase):
    ARQ = RAIZ / "exemplos" / "reprovados" / "06-excecoes.yaml"

    def nivel_2_3(self, hoje, objeto):
        rel, _ = check_padrao.verifica([self.ARQ], hoje=hoje)
        return {a[0] for a in rel.achados if a[1] == "2.3" and a[3] == objeto}

    def test_valida_vira_aviso(self):
        self.assertEqual(self.nivel_2_3(datetime.date(2026, 10, 1), "Deployment/nyx-api"), {"AVISO"})

    def test_vence_no_dia_seguinte_a_validade(self):
        ultimo_dia = datetime.date(2026, 1, 31)
        self.assertEqual(self.nivel_2_3(ultimo_dia, "Deployment/nyx-admin"), {"AVISO"})
        self.assertEqual(self.nivel_2_3(ultimo_dia + datetime.timedelta(days=1),
                                        "Deployment/nyx-admin"), {"ERRO"})


class Imagens(unittest.TestCase):
    def achados_3x(self, imagem):
        rel = check_padrao.Relatorio(datetime.date.today())
        obj = {"kind": "Pod", "metadata": {"name": "p", "namespace": "nyx-dev"},
               "spec": {"containers": [{"name": "api", "image": imagem}]}}
        check_padrao.bloco3(rel, check_padrao.Ctx("x", obj), check_padrao.indexa([]))
        return {a[1] for a in rel.achados if a[1] in ("3.1", "3.7")}

    def test_tag_imutavel_passa(self):
        self.assertEqual(self.achados_3x("registry.metacortex.io/nyx/api:2.9.1"), set())

    def test_digest_passa(self):
        self.assertEqual(self.achados_3x("registry.metacortex.io/nyx/api@sha256:" + "a" * 64), set())

    def test_sem_tag_equivale_a_latest(self):
        self.assertEqual(self.achados_3x("registry.metacortex.io/nyx/api"), {"3.1"})

    def test_porta_do_registry_nao_e_tag(self):
        self.assertEqual(self.achados_3x("registry.metacortex.io:5000/nyx/api"), {"3.1", "3.7"})

    def test_docker_hub_implicito(self):
        # O Trivy (KSV-0125) nao marca imagem sem dominio; o verificador marca.
        self.assertEqual(self.achados_3x("nginx:1.27"), {"3.7"})


class Nomes(unittest.TestCase):
    def test_kebab(self):
        for nome, ok in [("nyx-api", True), ("nyx2-api", True), ("NyxAPI", False),
                         ("nyx_api", False), ("nyx.api", False), ("nyx--api", False),
                         ("-nyx", False), ("nyx-", False), ("2fa-api", True)]:
            with self.subTest(nome=nome):
                self.assertEqual(bool(check_padrao.KEBAB.match(nome)), ok)

    def test_namespace(self):
        for ns, ok in [("nyx-prod", True), ("orion-stg", True), ("helio-dev", True),
                       ("nyx", False), ("nyx-production", False), ("nyx-hml", False),
                       ("nyx-prod-2", False), ("acme-corp-prod", True)]:
            with self.subTest(ns=ns):
                self.assertEqual(bool(check_padrao.NAMESPACE.match(ns)), ok)


if __name__ == "__main__":
    unittest.main()
