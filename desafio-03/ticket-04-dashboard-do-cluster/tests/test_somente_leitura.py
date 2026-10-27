"""RNF-01 no codigo: so leitura.py importa `kubernetes`, e ele so chama list_*/read_*."""
import ast
import pathlib
import unittest

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "retrato"
PROIBIDOS = ("create_", "patch_", "replace_", "delete_", "connect_", "call_api")
CHAMADAS_DA_API = ("core.", "apps.", "discovery.")


def verifica(arquivos):
    """Devolve a lista de violacoes (vazia = so leitura)."""
    problemas = []
    for arq in arquivos:
        arvore = ast.parse(arq.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, (ast.Import, ast.ImportFrom)):
                mods = [a.name for a in no.names] if isinstance(no, ast.Import) else [no.module or ""]
                if any(m.split(".")[0] == "kubernetes" for m in mods) and arq.name != "leitura.py":
                    problemas.append("{}: importa kubernetes".format(arq.name))
            if isinstance(no, ast.Attribute):
                if no.attr.startswith(PROIBIDOS):
                    problemas.append("{}:{}: {}".format(arq.name, no.lineno, no.attr))
                alvo = ast.unparse(no)
                if alvo.startswith(tuple("self." + c for c in CHAMADAS_DA_API)) and \
                        not no.attr.startswith(("list_", "read_")):
                    problemas.append("{}:{}: {} nao e list_/read_".format(arq.name, no.lineno, alvo))
    return problemas


class TestSomenteLeitura(unittest.TestCase):
    def test_codigo_so_le(self):
        self.assertEqual(verifica(sorted(SRC.rglob("*.py"))), [])

    def test_o_verificador_pega_escrita(self):
        # Prova de que o teste acima nao passa por vacuidade.
        falso = SRC.parent.parent / "tests" / "_escrita_de_mentira.py"
        falso.write_text("from kubernetes import client\n"
                         "class X:\n    def f(self):\n        self.core.create_namespace(body=None)\n"
                         "        self.apps.patch_namespaced_deployment('a', 'b', {})\n")
        try:
            problemas = verifica([falso])
        finally:
            falso.unlink()
        self.assertTrue(any("importa kubernetes" in p for p in problemas))
        self.assertTrue(any("create_namespace" in p for p in problemas))
        self.assertTrue(any("patch_namespaced_deployment" in p for p in problemas))


if __name__ == "__main__":
    unittest.main()
