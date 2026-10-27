"""JSON (Roster) e Markdown (plantao), os dois a partir do mesmo resultado."""
import json

ROTULO = {"critico": "crítico", "alto": "alto", "medio": "médio"}
ORDEM = {"critico": 0, "alto": 1, "medio": 2}


def resultado(host, inventario, conformidade, resumo):
    return {"host": host, "inventario": inventario, "conformidade": conformidade, "resumo": resumo}


def em_json(res):
    return json.dumps(res, ensure_ascii=False, indent=2)


def _lista(valores):
    return ", ".join(str(v) for v in valores)


def _texto(v):
    if v is True or v is False:
        return str(v).lower()
    if isinstance(v, list):
        return _lista(v)
    return str(v)


def _esperado_md(e):
    r, esp = e["regra"], e["esperado"]
    if r == "servicos.ativos":
        faltam = (e["encontrado"] or {}).get("ausentes") if isinstance(e["encontrado"], dict) else None
        alvo = faltam or esp
        return "{} {}".format(_lista(alvo), "ativo" if len(alvo) == 1 else "ativos")
    if r == "servicos.proibidos":
        return "{} inativos".format(_lista(esp))
    if r == "portas_em_escuta.publicas_permitidas":
        return "só {} pública".format(_lista(esp))
    if r == "portas_em_escuta.somente_rede_interna":
        return "{} na rede interna".format(_lista(esp))
    if r == "chaves_ssh.emitidas_por":
        return "todas emitidas por {}".format(esp)
    return _texto(esp)


def _encontrado_md(e):
    r, enc = e["regra"], e["encontrado"]
    if r == "servicos.ativos" and isinstance(enc, dict):
        return "ausente" if len(enc["ausentes"]) == 1 else "ausentes"
    if r == "servicos.proibidos" and isinstance(enc, dict):
        return "{} {}".format(_lista(enc["ativos"]), "ativo" if len(enc["ativos"]) == 1 else "ativos")
    if r == "portas_em_escuta.publicas_permitidas" and isinstance(enc, dict):
        return _lista("{} em {}{}".format(p["porta"], p["bind"],
                                          " ({})".format(p["processo"]) if p["processo"] else "")
                      for p in enc["nao_permitidas"])
    if r == "chaves_ssh.emitidas_por" and isinstance(enc, dict):
        return _lista(enc["nao_emitidas"])
    return _texto(enc)


def _celula(t):
    return str(t).replace("|", "\\|")


def em_markdown(res, versao_baseline):
    h, conf = res["host"], res["conformidade"]
    quando = h["coletado_em"].replace("T", " ")[:16] + " UTC"
    linhas = ["# Inventário de {} ({})".format(h["hostname"] or "?", h["endereco"]),
              "Coletado em {} · baseline v{}".format(quando, versao_baseline)]

    desvios = sorted((e for e in conf if e["veredito"] == "desvio"),
                     key=lambda e: ORDEM[e["severidade"]])
    if desvios:
        linhas += ["", "## Desvios", "", "| Severidade | Regra | Esperado | Encontrado |",
                   "|---|---|---|---|"]
        linhas += ["| {} | {} | {} | {} |".format(ROTULO[e["severidade"]], e["regra"],
                                                   _celula(_esperado_md(e)), _celula(_encontrado_md(e)))
                   for e in desvios]

    nv = [e for e in conf if e["veredito"] == "nao_verificado"]
    if nv:
        linhas += ["", "## Não verificado", "", "| Regra | Motivo |", "|---|---|"]
        linhas += ["| {} | {} |".format(e["regra"], _celula(e["motivo"])) for e in nv]

    ok = [e["regra"] for e in conf if e["veredito"] == "conforme"]
    if ok:
        linhas += ["", "## Conforme", " · ".join(ok)]
    return "\n".join(linhas) + "\n"
