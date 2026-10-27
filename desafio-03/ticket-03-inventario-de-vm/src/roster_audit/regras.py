"""Inventario + baseline -> uma entrada de conformidade por regra (spec `conformidade`)."""
import ipaddress
import re

from roster_audit.baseline import REGRAS, esperado

NAO_COLETADO = "dado não coletado"


def versao(texto):
    """'5.15.0-118-generic' -> (5, 15, 0); '22.04.4' -> (22, 4, 4)."""
    m = re.match(r"(\d+(?:\.\d+)*)", str(texto or ""))
    return tuple(int(p) for p in m.group(1).split(".")) if m else None


def maior_ou_igual(encontrada, minima):
    a, b = versao(encontrada), versao(minima)
    if a is None or b is None:
        return None
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) >= b + (0,) * (n - len(b))


def classe_do_bind(bind):
    """loopback | publico | interno (TRD §3)."""
    if bind in ("*", "0.0.0.0", "::"):
        return "publico"
    try:
        ip = ipaddress.ip_address(bind)
    except ValueError:
        return "publico"
    if ip.is_loopback:
        return "loopback"
    if ip.version == 4 and ip.is_private and not ip.is_link_local:
        return "interno"
    if ip.version == 6 and ip in ipaddress.ip_network("fc00::/7"):
        return "interno"
    return "publico"


class Avaliacao:
    def __init__(self, baseline, inventario, meta):
        self.b, self.inv, self.meta = baseline, inventario, meta
        self.falhas = meta["falhas"]

    def motivo(self, *secoes):
        for s in secoes:
            if s in self.falhas:
                return self.falhas[s]
        return NAO_COLETADO

    def entrada(self, regra, encontrado, ok, motivo=None):
        e = {"regra": regra, "esperado": esperado(self.b, regra), "encontrado": encontrado}
        if ok is None:
            e.update(encontrado=None, veredito="nao_verificado", motivo=motivo or NAO_COLETADO)
        elif ok:
            e["veredito"] = "conforme"
        else:
            e.update(veredito="desvio", severidade=self.b["_severidade"][regra])
        return e

    # --- uma funcao por regra, na ordem de REGRAS -----------------------------

    def so_distribuicao(self, r):
        so = self.inv["so"]
        if not so:
            return self.entrada(r, None, None, self.motivo("os_release"))
        return self.entrada(r, so["distribuicao"], so["distribuicao"] == esperado(self.b, r))

    def so_versao_minima(self, r):
        so = self.inv["so"]
        if not so or not so.get("versao"):
            return self.entrada(r, None, None, self.motivo("os_release"))
        return self.entrada(r, so["versao"], maior_ou_igual(so["versao"], esperado(self.b, r)))

    def kernel_versao_minima(self, r):
        k = self.inv["kernel"]["versao"]
        if not k:
            return self.entrada(r, None, None, self.motivo("kernel"))
        return self.entrada(r, k, maior_ou_igual(k, esperado(self.b, r)))

    def _ativas(self):
        return {u["nome"] for u in self.inv["servicos"]}

    def servicos_ativos(self, r):
        if self.inv["servicos"] is None:
            return self.entrada(r, None, None, self.motivo("units"))
        ativas = self._ativas()
        ausentes = [s for s in esperado(self.b, r)
                    if s + ".service" not in ativas and s + ".socket" not in ativas]
        enc = "todos ativos" if not ausentes else {"ausentes": ausentes}
        return self.entrada(r, enc, not ausentes)

    def servicos_proibidos(self, r):
        if self.inv["servicos"] is None:
            return self.entrada(r, None, None, self.motivo("units"))
        ativos = sorted(set(esperado(self.b, r)) & self._ativas())
        enc = "nenhum ativo" if not ativos else {"ativos": ativos}
        return self.entrada(r, enc, not ativos)

    def swap_habilitado(self, r):
        sw = self.inv["swap"]
        if sw is None:
            return self.entrada(r, None, None, self.motivo("swaps"))
        enc = "true ({})".format(sw["tamanho"]) if sw["habilitado"] else False
        return self.entrada(r, enc, sw["habilitado"] == esperado(self.b, r))

    def _publicas(self):
        return [p for p in self.inv["portas_em_escuta"] if classe_do_bind(p["bind"]) == "publico"]

    def portas_publicas(self, r):
        if self.inv["portas_em_escuta"] is None:
            return self.entrada(r, None, None, self.motivo("listen"))
        permitidas = set(esperado(self.b, r))
        internas = set(esperado(self.b, "portas_em_escuta.somente_rede_interna"))
        extra = sorted({p["porta"] for p in self._publicas()} - permitidas - internas)
        enc = "só {}".format(sorted(permitidas)) if not extra else {
            "nao_permitidas": [{"porta": p["porta"], "bind": p["bind"], "processo": p["processo"]}
                               for p in self._publicas() if p["porta"] in extra]}
        return self.entrada(r, enc, not extra)

    def portas_internas(self, r):
        if self.inv["portas_em_escuta"] is None:
            return self.entrada(r, None, None, self.motivo("listen"))
        alvo = set(esperado(self.b, r))
        expostas = [p for p in self._publicas() if p["porta"] in alvo]
        if expostas:
            enc = ["{} em {}".format(p["porta"], p["bind"]) for p in expostas]
            return self.entrada(r, enc, False)
        vistas = [p for p in self.inv["portas_em_escuta"] if p["porta"] in alvo]
        enc = ["{} em {}".format(p["porta"], p["bind"]) for p in vistas] or "não estão em escuta"
        return self.entrada(r, enc, True)

    def chaves(self, r):
        ch = self.inv["chaves_ssh"]
        if ch is None:
            return self.entrada(r, None, None, self.motivo("authkeys_all", "authkeys_self"))
        sufixo = "@" + esperado(self.b, r)
        estranhas = [c for c in ch if not (c["identificacao"] or "").endswith(sufixo)]
        if estranhas:
            # Evidencia parcial ja condena (ADR-0002, item 4).
            return self.entrada(r, {"nao_emitidas": [
                "{}: {}".format(c["conta"], c["identificacao"] or "(sem comentário)")
                for c in estranhas]}, False)
        if self.meta["cobertura_chaves"] != "todas_as_contas":
            return self.entrada(r, None, None,
                                "só a conta da coleta ({}) foi lida, e {} da plataforma; as outras "
                                "contas exigem privilégio (use --sudo)".format(
                                    self.meta["usuario_coleta"],
                                    "a única chave dela é" if len(ch) == 1
                                    else "as {} chaves dela são".format(len(ch))))
        return self.entrada(r, "{} chave(s), todas da plataforma".format(len(ch)), True)

    def login_de_root(self, r):
        valor = self.inv["ssh"].get("permitrootlogin")
        if valor is None:
            return self.entrada(r, None, None, self.motivo("sshd_t"))
        permitido = valor != "no"
        enc = "true ({})".format(valor) if permitido else False
        return self.entrada(r, enc, permitido == esperado(self.b, r))

    def ntp(self, r):
        n = self.inv["ntp"]
        if n is None:
            return self.entrada(r, None, None, self.motivo("timedatectl"))
        return self.entrada(r, n["sincronizado"], n["sincronizado"] == esperado(self.b, r))


FUNCOES = dict(zip(REGRAS, (
    Avaliacao.so_distribuicao, Avaliacao.so_versao_minima, Avaliacao.kernel_versao_minima,
    Avaliacao.servicos_ativos, Avaliacao.servicos_proibidos, Avaliacao.swap_habilitado,
    Avaliacao.portas_publicas, Avaliacao.portas_internas, Avaliacao.chaves,
    Avaliacao.login_de_root, Avaliacao.ntp,
)))


def avalia(baseline, inventario, meta):
    av = Avaliacao(baseline, inventario, meta)
    conformidade = [FUNCOES[r](av, r) for r in REGRAS]
    resumo = {"conforme": 0, "desvio": 0, "nao_verificado": 0,
              "por_severidade": {"critico": 0, "alto": 0, "medio": 0}}
    for e in conformidade:
        resumo[e["veredito"]] += 1
        if e["veredito"] == "desvio":
            resumo["por_severidade"][e["severidade"]] += 1
    return conformidade, resumo
