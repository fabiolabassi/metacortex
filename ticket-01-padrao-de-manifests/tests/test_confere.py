"""Cada anti-padrao reprova exatamente nas regras que declara na 1a linha, os
manifests de referencia passam limpos e o manifesto barrado do nyx reprova nas
11 regras levantadas na conferencia. Uso: python3 -m unittest discover -s tests"""
import pathlib
import sys
import unittest

AQUI = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AQUI / "skill" / "padrao-de-manifests" / "scripts"))
import confere  # noqa: E402

REPROVADOS = AQUI / "trabalho-anterior" / "exemplos" / "reprovados"


def regras_com_erro(alvo):
    achados, _, _ = confere.confere([str(alvo)])
    return {a.regra for a in achados if a.nivel == "ERRO"}


class TestConfere(unittest.TestCase):
    def test_anti_padroes(self):
        for arq in sorted(REPROVADOS.glob("*.yaml")):
            espera = set(arq.read_text().splitlines()[0].split("espera:")[1].split())
            with self.subTest(arq.name):
                self.assertEqual(regras_com_erro(arq), espera)

    def test_referencia_passa(self):
        self.assertEqual(regras_com_erro(AQUI / "trabalho-anterior" / "manifests"), set())

    def test_barrado_do_nyx(self):
        alvo = AQUI / "execucoes" / "conferencia-nyx-barrado" / "nyx-api-barrado.yaml"
        self.assertEqual(regras_com_erro(alvo), {"1.1", "1.3", "1.4", "2.1", "2.2", "2.3",
                                                  "2.4", "3.1", "3.2", "3.3", "3.4"})


if __name__ == "__main__":
    unittest.main()
