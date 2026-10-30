"""Testes do roster-audit sem SSH: parser com saidas reais das VMs de teste,
regras com inventarios sinteticos, classificacao de erros e codigos de saida.

    PYTHONPATH=src python3 -m unittest discover -s tests -v
"""
import copy
import io
import json
import pathlib
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from roster_audit import baseline, cli, conexao, parser, regras, saida

FIX = pathlib.Path(__file__).parent / "fixtures"
BASE = baseline.carrega()


def avalia_fixture(nome):
    host, inv, meta = parser.interpreta((FIX / nome).read_text(), "127.0.0.1", "2026-10-26T00:00:00Z")
    conf, resumo = regras.avalia(BASE, inv, meta)
    return host, inv, meta, {e["regra"]: e for e in conf}, resumo


class TestParserComSaidaReal(unittest.TestCase):
    def test_conforme_com_sudo_tudo_conforme(self):
        host, inv, _, conf, resumo = avalia_fixture("conforme-sudo1.txt")
        self.assertEqual(host["hostname"], "construct-node-01")
        self.assertEqual(resumo["conforme"], 11, {r: e for r, e in conf.items() if e["veredito"] != "conforme"})
        self.assertEqual(inv["so"]["distribuicao"], "ubuntu")
        self.assertIn({"porta": 9100, "bind": "10.0.2.15", "processo": "node_exporter"},
                      inv["portas_em_escuta"])

    def test_conforme_sem_sudo_dois_nao_verificados(self):
        _, _, _, conf, resumo = avalia_fixture("conforme-sudo0.txt")
        self.assertEqual((resumo["conforme"], resumo["desvio"], resumo["nao_verificado"]), (9, 0, 2))
        self.assertEqual(conf["ssh.login_de_root"]["veredito"], "nao_verificado")
        self.assertIn("privilégio", conf["ssh.login_de_root"]["motivo"])
        self.assertEqual(conf["chaves_ssh.emitidas_por"]["veredito"], "nao_verificado")

    def test_interface_no_bind_e_removida(self):
        _, inv, _, _, _ = avalia_fixture("conforme-sudo0.txt")
        self.assertTrue(all("%" not in p["bind"] for p in inv["portas_em_escuta"]))

    def test_desvios(self):
        if not (FIX / "desvios-sudo1.txt").exists():
            self.skipTest("fixture da VM de desvios ainda nao capturada")
        _, _, _, conf, resumo = avalia_fixture("desvios-sudo1.txt")
        esperado = {"swap.habilitado": "critico", "chaves_ssh.emitidas_por": "critico",
                    "portas_em_escuta.publicas_permitidas": "critico",
                    "portas_em_escuta.somente_rede_interna": "critico",
                    "servicos.ativos": "alto", "servicos.proibidos": "alto", "ssh.login_de_root": "alto",
                    "kernel.versao_minima": "medio"}
        achado = {r: e["severidade"] for r, e in conf.items() if e["veredito"] == "desvio"}
        self.assertEqual(achado, esperado)


class TestSecoes(unittest.TestCase):
    def test_rc_diferente_de_zero_e_falha(self):
        _, inv, meta = parser.interpreta("##RA## swaps rc=1\n", "h", "t")
        self.assertIsNone(inv["swap"])
        self.assertIn("swaps", meta["falhas"])

    def test_swap_vazio_nao_e_falha(self):
        _, inv, meta = parser.interpreta(
            "##RA## swaps rc=0\nFilename Type Size Used Priority\n", "h", "t")
        self.assertEqual(inv["swap"], {"habilitado": False, "tamanho": None})
        self.assertNotIn("swaps", meta["falhas"])

    def test_secao_ausente_e_falha(self):
        _, inv, meta = parser.interpreta("##RA## hostname rc=0\nx\n", "h", "t")
        self.assertIsNone(inv["servicos"])
        self.assertEqual(meta["falhas"]["units"], "seção ausente na coleta")

    def test_swap_tamanho(self):
        _, inv, _ = parser.interpreta(
            "##RA## swaps rc=0\nFilename Type Size Used Priority\n/swapfile file 4194300 0 -2\n", "h", "t")
        self.assertEqual(inv["swap"], {"habilitado": True, "tamanho": "4G"})

    def test_chave_com_opcoes(self):
        ch = parser._chaves(['no-pty,command="echo x" ssh-ed25519 AAAA platform@metacortex-platform'],
                            conta="root")
        self.assertEqual(ch[0]["identificacao"], "platform@metacortex-platform")


class TestRegras(unittest.TestCase):
    def setUp(self):
        _, self.inv, self.meta, _, _ = avalia_fixture("conforme-sudo1.txt")

    def regra(self, nome, inv=None, meta=None):
        conf, _ = regras.avalia(BASE, inv or self.inv, meta or self.meta)
        return {e["regra"]: e for e in conf}[nome]

    def test_versoes(self):
        self.assertFalse(regras.maior_ou_igual("5.15.0-118-generic", "6.5"))
        self.assertTrue(regras.maior_ou_igual("22.04.4", "22.04"))
        self.assertTrue(regras.maior_ou_igual("6.8.0-147-generic", "6.5"))

    def test_classes_de_bind(self):
        for bind, classe in [("0.0.0.0", "publico"), ("::", "publico"), ("*", "publico"),
                             ("10.0.2.15", "interno"), ("192.168.1.4", "interno"),
                             ("127.0.0.53", "loopback"), ("::1", "loopback"),
                             ("200.1.2.3", "publico"), ("fd00::1", "interno")]:
            self.assertEqual(regras.classe_do_bind(bind), classe, bind)

    def test_9100_em_todas_as_interfaces_conta_so_uma_vez(self):
        inv = copy.deepcopy(self.inv)
        for p in inv["portas_em_escuta"]:
            if p["porta"] == 9100:
                p["bind"] = "0.0.0.0"
        self.assertEqual(self.regra("portas_em_escuta.somente_rede_interna", inv)["veredito"], "desvio")
        self.assertEqual(self.regra("portas_em_escuta.publicas_permitidas", inv)["veredito"], "conforme")

    def test_chave_estranha_condena_mesmo_sem_cobertura_total(self):
        inv, meta = copy.deepcopy(self.inv), dict(self.meta, cobertura_chaves="propria_conta")
        inv["chaves_ssh"].append({"conta": "auditor", "tipo": "ssh-ed25519", "identificacao": "dozer@notebook"})
        e = self.regra("chaves_ssh.emitidas_por", inv, meta)
        self.assertEqual((e["veredito"], e["severidade"]), ("desvio", "critico"))

    def test_prohibit_password_e_login_permitido(self):
        inv = copy.deepcopy(self.inv)
        inv["ssh"] = {"login_de_root": True, "permitrootlogin": "prohibit-password"}
        self.assertEqual(self.regra("ssh.login_de_root", inv)["veredito"], "desvio")

    def test_servico_por_socket_conta_como_ativo(self):
        inv = copy.deepcopy(self.inv)
        inv["servicos"] = [u for u in inv["servicos"] if u["nome"] != "ssh.service"]
        inv["servicos"].append({"nome": "ssh.socket", "tipo": "socket", "estado": "active"})
        self.assertEqual(self.regra("servicos.ativos", inv)["veredito"], "conforme")

    def test_nao_verificado_nunca_conta_como_conforme(self):
        inv = copy.deepcopy(self.inv)
        inv["ntp"] = None
        _, resumo = regras.avalia(BASE, inv, self.meta)
        self.assertEqual((resumo["conforme"], resumo["nao_verificado"]), (10, 1))


class TestSaida(unittest.TestCase):
    def test_markdown_e_json_tem_as_mesmas_contagens(self):
        if not (FIX / "desvios-sudo0.txt").exists():
            self.skipTest("fixture da VM de desvios ainda nao capturada")
        host, inv, meta = parser.interpreta((FIX / "desvios-sudo0.txt").read_text(), "h", "2026-10-26T00:00:00Z")
        conf, resumo = regras.avalia(BASE, inv, meta)
        res = saida.resultado(host, inv, conf, resumo)
        md = saida.em_markdown(res, 1)
        desvios_md = md.split("## Desvios")[1].split("##")[0]
        linhas = [l for l in desvios_md.splitlines() if l.startswith("| ") and "Severidade" not in l]
        self.assertEqual(len(linhas), json.loads(saida.em_json(res))["resumo"]["desvio"])


class TestErros(unittest.TestCase):
    CTX = {"endereco": "10.0.0.9", "porta": 22, "usuario": "auditor", "timeout": 10}

    def test_classificacao(self):
        casos = {
            "ssh: connect to host 10.0.0.9 port 22: Connection refused": "recusou a conexão",
            "ssh: connect to host 10.0.0.9 port 22: Connection timed out": "não respondeu em 10s",
            "auditor@10.0.0.9: Permission denied (publickey).": "recusou a chave para o usuário auditor",
            "ssh: Could not resolve hostname x: Name or service not known": "não foi possível resolver",
            "No ED25519 host key is known for 10.0.0.9 and you have requested strict checking.\n"
            "Host key verification failed.": "--aceitar-host-novo",
            "@ WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED! @\nHost key verification failed.": "MUDOU",
            'Load key "/home/x/.ssh/segredo": bad permissions': "permissão aberta demais",
            "algo novo": "não classificada",
        }
        for stderr, trecho in casos.items():
            with self.subTest(stderr=stderr):
                msg = conexao.classifica(stderr, **self.CTX)
                self.assertIn(trecho, msg)
                self.assertNotIn("/home/x", msg)

    def test_chave_inexistente_e_erro_de_uso(self):
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()):
            rc = cli.main(["--endereco", "h", "--usuario", "u", "--chave", "/nao/existe/segredo"])
        self.assertEqual(rc, 3)
        self.assertNotIn("/nao/existe", err.getvalue())

    def test_host_inalcancavel_codigo_4_sem_stdout(self):
        falso = subprocess.CompletedProcess([], 255, "", "ssh: connect to host h port 22: Connection refused")
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("subprocess.run", return_value=falso), \
                mock.patch.object(conexao, "verifica_chave"), redirect_stdout(out), redirect_stderr(err):
            rc = cli.main(["--endereco", "h", "--usuario", "u", "--chave", "k"])
        self.assertEqual((rc, out.getvalue()), (4, ""))
        self.assertNotIn("Traceback", err.getvalue())

    def test_falha_inesperada_sem_traceback(self):
        err = io.StringIO()
        with mock.patch.object(cli, "executa", side_effect=ZeroDivisionError), \
                redirect_stderr(err), redirect_stdout(io.StringIO()):
            rc = cli.main(["--endereco", "h", "--usuario", "u", "--chave", "k"])
        self.assertEqual(rc, 4)
        self.assertNotIn("Traceback", err.getvalue())

    def test_argumento_faltando_e_codigo_3(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as cm:
            cli.main(["--endereco", "h"])
        self.assertEqual(cm.exception.code, 3)


if __name__ == "__main__":
    unittest.main()
