"""Secoes ##RA## -> inventario (formato do JSON de saida) + falhas.

Regra da ADR-0002: secao ausente, rc != 0 ou saida ininteligivel e FALHA (o
campo fica None e `falhas[secao]` guarda o motivo). Saida vazia legitima
(sem swap, sem chave) NAO e falha.
"""
import re

MARCA = re.compile(r"^##RA## (\S+) rc=(\d+)$")

MOTIVO_PRIVILEGIO = "exige privilégio que o usuário da coleta não tem"
MOTIVOS = {
    "sshd_t": MOTIVO_PRIVILEGIO + " (sshd -T precisa de root; use --sudo)",
    "authkeys_all": MOTIVO_PRIVILEGIO + " (chaves das outras contas; use --sudo)",
}


def secoes(texto):
    """{nome: (rc, linhas)}. Linhas vazias do fim sao descartadas."""
    out, atual = {}, None
    for linha in texto.splitlines():
        m = MARCA.match(linha)
        if m:
            atual = m.group(1)
            out[atual] = (int(m.group(2)), [])
        elif atual:
            out[atual][1].append(linha)
    return {k: (rc, _apara(ls)) for k, (rc, ls) in out.items()}


def _apara(linhas):
    while linhas and not linhas[-1].strip():
        linhas = linhas[:-1]
    return linhas


def interpreta(texto, endereco, coletado_em):
    s = secoes(texto)
    falhas = {}

    def le(nome, motivo=None):
        if nome not in s:
            falhas[nome] = "seção ausente na coleta"
            return None
        rc, linhas = s[nome]
        if rc != 0:
            falhas[nome] = motivo or MOTIVOS.get(nome) or "comando falhou no host (rc={})".format(rc)
            return None
        return linhas

    inv = {
        "so": _so(le("os_release")),
        "kernel": {"versao": (le("kernel") or [None])[0]},
        "servicos": _unidades(le("units")),
        "swap": _swap(le("swaps")),
        "portas_em_escuta": _portas(le("listen")),
        "chaves_ssh": None,
        "ssh": {"login_de_root": None},
        "ntp": None,
    }
    if inv["so"] is None:
        falhas.setdefault("os_release", "os-release ilegível")
    if inv["portas_em_escuta"] is None and "listen" not in falhas:
        falhas["listen"] = "saída do ss ininteligível"

    # Chaves: todas as contas (com --sudo) ou so a propria.
    usuario = (le("whoami") or [None])[0]
    todas = le("authkeys_all")
    if todas is not None:
        inv["chaves_ssh"] = _chaves(todas, prefixada=True)
        cobertura = "todas_as_contas"
    else:
        propria = le("authkeys_self")
        inv["chaves_ssh"] = None if propria is None else _chaves(propria, conta=usuario)
        cobertura = None if propria is None else "propria_conta"

    sshd = le("sshd_t")
    if sshd is not None:
        valor = _sshd(sshd, "permitrootlogin")
        if valor is None:
            falhas["sshd_t"] = "sshd -T não informou permitrootlogin"
        else:
            inv["ssh"] = {"login_de_root": valor != "no", "permitrootlogin": valor}

    inv["ntp"] = _ntp(le("timedatectl"), inv["servicos"])

    host = {"endereco": endereco, "hostname": (le("hostname") or [None])[0],
            "coletado_em": coletado_em}
    meta = {"falhas": falhas, "cobertura_chaves": cobertura, "usuario_coleta": usuario}
    return host, inv, meta


def _so(linhas):
    if not linhas:
        return None
    kv = {}
    for linha in linhas:
        if "=" in linha:
            k, v = linha.split("=", 1)
            kv[k] = v.strip().strip('"')
    if "ID" not in kv:
        return None
    versao = kv.get("VERSION_ID")
    # VERSION="22.04.4 LTS (Jammy Jellyfish)" traz o ponto; VERSION_ID so "22.04".
    m = re.match(r"(\d+(?:\.\d+)+)", kv.get("VERSION", ""))
    if m and versao and m.group(1).startswith(versao):
        versao = m.group(1)
    return {"distribuicao": kv["ID"], "versao": versao}


def _unidades(linhas):
    if linhas is None:
        return None
    out = []
    for linha in linhas:
        partes = linha.split()
        if len(partes) < 4 or "." not in partes[0]:
            continue
        nome, _load, ativo, _sub = partes[:4]
        out.append({"nome": nome, "tipo": nome.rsplit(".", 1)[1], "estado": ativo})
    return sorted(out, key=lambda u: u["nome"])


def _swap(linhas):
    if linhas is None:
        return None
    total_kib = 0
    for linha in linhas[1:]:  # 1a linha e o cabecalho
        partes = linha.split()
        if len(partes) >= 3 and partes[2].isdigit():
            total_kib += int(partes[2])
    if not total_kib:
        return {"habilitado": False, "tamanho": None}
    return {"habilitado": True, "tamanho": _humano(total_kib)}


def _humano(kib):
    for unidade, fator in (("G", 1024 ** 2), ("M", 1024)):
        if kib >= fator:
            valor = kib / fator
            # /proc/swaps desconta uma pagina: 512M aparece como 524284 KiB.
            inteiro = abs(valor - round(valor)) < 0.05
            return ("{:.0f}{}" if inteiro else "{:.1f}{}").format(valor, unidade)
    return "{}K".format(kib)


PROCESSO = re.compile(r'users:\(\("([^"]+)"')


def _portas(linhas):
    if linhas is None:
        return None
    vistos = set()
    for linha in linhas:
        partes = linha.split()
        # ss -H -t -l -n -p: State Recv-Q Send-Q Local Peer [Process]
        if len(partes) < 5:
            continue
        local = partes[3]
        if ":" not in local:
            return None
        bind, porta = local.rsplit(":", 1)
        bind = bind.strip("[]").split("%", 1)[0]  # "127.0.0.53%lo" -> "127.0.0.53"
        if not porta.isdigit():
            continue
        m = PROCESSO.search(linha)
        vistos.add((int(porta), bind, m.group(1) if m else None))
    return [{"porta": p, "bind": b, "processo": pr}
            for p, b, pr in sorted(vistos, key=lambda x: (x[0], x[1], x[2] or ""))]


TIPOS_CHAVE = re.compile(r"^(ssh-|ecdsa-|sk-)")


def _chaves(linhas, prefixada=False, conta=None):
    out = []
    for linha in linhas:
        if prefixada:
            if " " not in linha:
                continue
            conta, linha = linha.split(" ", 1)
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        campos = linha.split()
        # Opcoes (command="...",no-pty) podem vir antes do tipo da chave.
        i = next((n for n, c in enumerate(campos) if TIPOS_CHAVE.match(c)), None)
        if i is None or len(campos) < i + 2:
            continue
        comentario = " ".join(campos[i + 2:]) or None
        out.append({"conta": conta, "tipo": campos[i], "identificacao": comentario})
    return sorted(out, key=lambda c: (c["conta"] or "", c["identificacao"] or "", c["tipo"]))


def _sshd(linhas, chave):
    for linha in linhas:
        partes = linha.split(None, 1)
        if len(partes) == 2 and partes[0].lower() == chave:
            return partes[1].strip()
    return None


MECANISMOS = ("chrony", "systemd-timesyncd", "ntpsec", "ntp", "openntpd")


def _ntp(linhas, unidades):
    mecanismo = None
    for m in MECANISMOS:
        if any(u["nome"] == m + ".service" for u in unidades or []):
            mecanismo = m
            break
    if linhas is None:
        return None
    kv = dict(linha.split("=", 1) for linha in linhas if "=" in linha)
    if "NTPSynchronized" not in kv:
        return None
    return {"sincronizado": kv["NTPSynchronized"] == "yes", "mecanismo": mecanismo}
