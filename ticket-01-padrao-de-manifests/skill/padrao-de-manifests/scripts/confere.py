#!/usr/bin/env python3
"""Conferencia mecanica do Padrao de Manifests da Metacortex.

Roda o Trivy (o que ele ja cobre) e, em seguida, as regras que o Trivy nao
conhece. Junta tudo num relatorio por regra do padrao. Uso:

    python3 confere.py CAMINHO [CAMINHO ...] [--sem-trivy]

So confere o que se decide olhando o YAML. O que depende de ler o projeto
(endpoint de probe existe? valor de limits faz sentido? a tag e a promovida?)
nao esta aqui: e instrucao do SKILL.md.

Saida: 0 sem ERRO, 1 com ERRO, 2 erro de uso (caminho inexistente, YAML
invalido).
"""
import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys

import yaml

AQUI = pathlib.Path(__file__).resolve().parent
TRIVY_DATA = AQUI.parent / "assets" / "trivy-data"
TRIVY_IGNORE = AQUI.parent / "assets" / "trivyignore.yaml"

# --- o que o Trivy ja cobre: KSV -> regra do padrao ---------------------------
# Levantado rodando `trivy config` (v0.74.0) no manifesto barrado e em
# manifests de teste. Ver references/trivy.md.
KSV_PARA_REGRA = {
    "KSV-0011": "2.1", "KSV-0015": "2.1", "KSV-0016": "2.1", "KSV-0018": "2.1",
    "KSV-0013": "3.1",
    "KSV-0001": "3.2", "KSV-0003": "3.2", "KSV-0004": "3.2", "KSV-0012": "3.2",
    "KSV-0014": "3.2", "KSV-0020": "3.2", "KSV-0021": "3.2", "KSV-0030": "3.2",
    "KSV-0104": "3.2", "KSV-0106": "3.2", "KSV-0118": "3.2",
    "KSV-0109": "3.3",
    "KSV-0036": "3.4",
    "KSV-0008": "3.6", "KSV-0009": "3.6", "KSV-0010": "3.6", "KSV-0017": "3.6",
    "KSV-0125": "3.7",
}
# Pedem mais do que o texto da 3.2: viram AVISO. seccompProfile e cobrado pelo
# Pod Security 'restricted', entao o modelo declara mesmo assim.
ALEM_DO_PADRAO = {"KSV-0021", "KSV-0030", "KSV-0104"}
REGRAS_DO_TRIVY = sorted(set(KSV_PARA_REGRA.values()) - {"3.3", "3.4", "3.7"})

# --- constantes do padrao ------------------------------------------------------
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")                                  # 1.1
NAMESPACE = re.compile(r"^(?P<cliente>[a-z0-9]+(?:-[a-z0-9]+)*)-(?P<amb>dev|stg|prod)$")  # 1.2
ROTULOS = ("app.kubernetes.io/name", "app.kubernetes.io/instance",                # 1.3
           "app.kubernetes.io/part-of", "app.kubernetes.io/managed-by")
MANAGED_BY = ("platform", "argocd", "helm")
NOMES_GENERICOS = {"app", "main", "container"}                                    # 1.6
CHAVE_SENSIVEL = re.compile(                                                      # 3.3
    r"(passw|senha|secret|token|api[-_]?key|credential|private[-_]?key|dsn)", re.I)
URL_COM_CREDENCIAL = re.compile(r"[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@", re.I)

COM_POD = {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet", "Job", "CronJob", "Pod"}
SEM_NAMESPACE = {"Namespace", "ClusterRole", "ClusterRoleBinding", "PersistentVolume",
                 "StorageClass", "CustomResourceDefinition", "PriorityClass"}
RECOMENDADAS = {"1.5", "1.6", "2.5", "2.6", "3.5"}


class Achado:
    def __init__(self, regra, arquivo, objeto, msg, origem, aviso=False):
        self.nivel = "AVISO" if aviso or regra in RECOMENDADAS else "ERRO"
        self.regra, self.arquivo, self.objeto, self.msg, self.origem = \
            regra, arquivo, objeto, msg, origem


class Obj:
    def __init__(self, arquivo, raw):
        md = raw.get("metadata") or {}
        self.arquivo, self.raw = arquivo, raw
        self.kind = raw.get("kind")
        self.nome = md.get("name", "")
        self.namespace = md.get("namespace")
        self.anotacoes = md.get("annotations") or {}
        self.rotulo = "{}/{}".format(self.kind, self.nome) if self.kind else "-"


# --- utilitarios -------------------------------------------------------------------

def amb(ns):
    m = NAMESPACE.match(ns or "")
    return m and m.group("amb")


def cliente(ns):
    m = NAMESPACE.match(ns or "")
    return m and m.group("cliente")


def metadatas(raw):
    """O metadata de tudo que vira objeto no cluster: o proprio, o Job de um
    CronJob e o Pod do template."""
    yield "", raw.get("metadata") or {}
    spec = raw.get("spec") or {}
    if raw.get("kind") == "CronJob":
        jt = spec.get("jobTemplate") or {}
        yield "jobTemplate ", jt.get("metadata") or {}
        spec = jt.get("spec") or {}
    if raw.get("kind") in COM_POD - {"Pod"}:
        yield "template do pod ", (spec.get("template") or {}).get("metadata") or {}


def pod_spec(raw):
    if raw.get("kind") == "Pod":
        return raw.get("spec") or {}
    spec = raw.get("spec") or {}
    if raw.get("kind") == "CronJob":
        spec = (spec.get("jobTemplate") or {}).get("spec") or {}
    return (spec.get("template") or {}).get("spec") or {}


def rotulos_do_pod(raw):
    return list(metadatas(raw))[-1][1].get("labels") or {}


def casa(seletor, rotulos):
    return bool(seletor) and all(rotulos.get(k) == v for k, v in seletor.items())


def portas(spec):
    """Portas nomeadas e numeros declarados pelos containers."""
    s = set()
    for c in spec.get("containers") or []:
        for p in c.get("ports") or []:
            s.add(p.get("containerPort"))
            if p.get("name"):
                s.add(p["name"])
    return s


# --- regras que o Trivy nao cobre --------------------------------------------------

def bloco1(o, add):
    if not KEBAB.match(o.nome) or len(o.nome) > 63:
        add("1.1", o, "nome '{}' fora de kebab-case".format(o.nome))

    ns = o.nome if o.kind == "Namespace" else o.namespace
    if o.kind not in SEM_NAMESPACE and not ns:
        add("1.2", o, "sem metadata.namespace — aterrissaria no namespace do contexto")
    elif ns and not NAMESPACE.match(ns):
        add("1.2", o, "namespace '{}' fora de <cliente>-<dev|stg|prod>".format(ns))

    for nivel, md in metadatas(o.raw):
        labels = md.get("labels") or {}
        faltam = [r for r in ROTULOS if r not in labels]
        if faltam:
            curto = " (o rotulo curto 'app' sozinho nao atende)" if "app" in labels else ""
            add("1.3", o, "{}sem {}{}".format(nivel, ", ".join(faltam), curto))
        mb = labels.get("app.kubernetes.io/managed-by")
        if mb is not None and mb not in MANAGED_BY:
            add("1.3", o, "{}managed-by '{}' fora de {}".format(nivel, mb, "|".join(MANAGED_BY)))
        inst = labels.get("app.kubernetes.io/instance")
        part = labels.get("app.kubernetes.io/part-of")
        if ns and NAMESPACE.match(ns):
            if inst is not None and inst != ns:
                add("1.3", o, "{}instance '{}' diferente do namespace '{}'".format(nivel, inst, ns))
            if part is not None and part != cliente(ns):
                add("1.3", o, "{}part-of '{}' diferente do cliente '{}'".format(
                    nivel, part, cliente(ns)))

    if not o.anotacoes.get("metacortex.io/owner"):
        add("1.5", o, "sem anotacao metacortex.io/owner")
    if o.kind in COM_POD and not o.anotacoes.get("metacortex.io/runbook"):
        add("1.5", o, "sem anotacao metacortex.io/runbook")


def seletor_do_workload(o, add):
    if o.kind not in {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet"}:
        return
    ml = ((o.raw.get("spec") or {}).get("selector") or {}).get("matchLabels") or {}
    labels = rotulos_do_pod(o.raw)
    for k, v in ml.items():
        if labels.get(k) != v:
            add("1.4", o, "matchLabels {}={} nao casa com o pod ({})".format(
                k, v, labels.get(k, "ausente")))


def seletor_do_service(o, idx, add):
    spec = o.raw.get("spec") or {}
    if spec.get("type") == "ExternalName":
        return
    sel = spec.get("selector") or {}
    if not sel:
        add("1.4", o, "Service sem seletor")
        return
    alvos = [w for w in idx["pods"].get(o.namespace, []) if casa(sel, w["labels"])]
    if not alvos:
        perto = [w["rotulo"] + " " + str(w["labels"]) for w in idx["pods"].get(o.namespace, [])]
        add("1.4", o, "seletor {} nao casa com nenhum pod do namespace — o Service sobe sem "
                      "endpoint. Pods no arquivo: {}".format(sel, "; ".join(perto) or "nenhum"))
        return
    for p in spec.get("ports") or []:
        tp = p.get("targetPort", p.get("port"))
        if not any(tp in w["portas"] or str(tp) in map(str, w["portas"]) for w in alvos):
            add("1.4", o, "targetPort {} nao e declarado por nenhum container selecionado".format(tp),
                aviso=isinstance(tp, int))


def seletor_do_pdb(o, idx, add):
    spec = o.raw.get("spec") or {}
    sel = (spec.get("selector") or {}).get("matchLabels") or {}
    alvos = [w for w in idx["pods"].get(o.namespace, []) if casa(sel, w["labels"])]
    if not alvos:
        add("1.4", o, "PDB nao seleciona nenhum pod")
    for w in alvos:
        mina = spec.get("minAvailable")
        if isinstance(mina, int) and mina >= w["replicas"]:
            add("2.5", o, "minAvailable={} com {} replicas trava o drain do no".format(
                mina, w["replicas"]))


def bloco2(o, idx, add):
    spec = pod_spec(o.raw)
    decl = portas(spec)
    longa = o.kind not in {"Job", "CronJob"}
    for c in spec.get("containers") or []:
        alvo = "container '{}'".format(c.get("name"))
        if c.get("name") in NOMES_GENERICOS:
            add("1.6", o, "{}: nome generico, use o do componente".format(alvo))
        if not longa:
            continue  # 2.2 nao se aplica a quem termina: ver references/regras.md
        for probe in ("readinessProbe", "livenessProbe"):
            p = c.get(probe)
            if not p:
                add("2.2", o, "{} sem {}".format(alvo, probe))
                continue
            porta = (p.get("httpGet") or p.get("tcpSocket") or p.get("grpc") or {}).get("port")
            if porta is not None and porta not in decl:
                add("2.2", o, "{} {} aponta para a porta {}, que o container nao declara".format(
                    alvo, probe, porta))
        r, l = c.get("readinessProbe"), c.get("livenessProbe")
        if r and l and (r.get("httpGet") or r.get("exec") or r.get("tcpSocket")) == \
                (l.get("httpGet") or l.get("exec") or l.get("tcpSocket")):
            add("2.2", o, "{}: readiness e liveness checam a mesma coisa — se ela depende do "
                          "banco, banco lento reinicia o pod".format(alvo))

    if amb(o.namespace) != "prod" or o.kind not in {"Deployment", "StatefulSet"}:
        return
    s = o.raw.get("spec") or {}
    replicas = s.get("replicas", 1)
    if replicas < 2:
        add("2.3", o, "replicas={} em prod".format(replicas))
    if o.kind == "Deployment":
        st = s.get("strategy") or {}
        ru = st.get("rollingUpdate") or {}
        if st.get("type", "RollingUpdate") != "RollingUpdate" or \
                str(ru.get("maxUnavailable", "25%")) != "0" or str(ru.get("maxSurge", "25%")) != "1":
            add("2.4", o, "prod exige RollingUpdate com maxUnavailable: 0 e maxSurge: 1 "
                          "(declarado: {})".format(st or "nada — default 25%/25%"))
    if replicas >= 2:
        labels = rotulos_do_pod(o.raw)
        if not any(casa(sel, labels) for sel in idx["pdbs"].get(o.namespace, [])):
            add("2.5", o, "{} replicas em prod sem PodDisruptionBudget".format(replicas))


def bloco3(o, idx, add):
    spec = pod_spec(o.raw)
    sa = spec.get("serviceAccountName") or spec.get("serviceAccount")
    if not sa or sa == "default":
        add("3.5", o, "usa a ServiceAccount default do namespace")
    elif len(idx["uso_sa"].get((o.namespace, sa), ())) > 1:
        add("3.5", o, "ServiceAccount '{}' compartilhada".format(sa))
    # KSV-0036 so dispara com `true` explicito; campo ausente passa no Trivy.
    automount = spec.get("automountServiceAccountToken")
    if automount is None:
        automount = idx["sa"].get((o.namespace, sa or "default"))
    if automount is None:
        add("3.4", o, "automountServiceAccountToken ausente no pod e na SA — o default e montar")

    for tipo in ("initContainers", "containers"):
        for c in spec.get(tipo) or []:
            alvo = "container '{}'".format(c.get("name"))
            img = c.get("image", "")
            # KSV-0125 ignora imagem sem dominio (Docker Hub implicito).
            primeiro = img.split("/", 1)[0]
            if "/" not in img or ("." not in primeiro and ":" not in primeiro
                                  and primeiro != "localhost"):
                add("3.7", o, "{}: imagem '{}' sem registry — vem do Docker Hub, fora de "
                              "registry.metacortex.io".format(alvo, img))
            for e in c.get("env") or []:
                if "value" in e and (CHAVE_SENSIVEL.search(e.get("name", ""))
                                     or URL_COM_CREDENCIAL.search(str(e["value"]))):
                    add("3.3", o, "{}: env {} em texto puro — use secretKeyRef".format(
                        alvo, e.get("name")))


def configmap_e_secret(o, add):
    if o.kind == "Secret":
        if o.raw.get("data") or o.raw.get("stringData"):
            add("3.3", o, "Secret com valor no arquivo — vai para o Git; crie fora do repositorio")
        return
    for k, v in (o.raw.get("data") or {}).items():
        if CHAVE_SENSIVEL.search(k) or URL_COM_CREDENCIAL.search(str(v)):
            add("3.3", o, "chave '{}' parece sensivel — ConfigMap nao guarda segredo".format(k))


def comentarios(arquivo, texto, add):
    """3.3 vale para comentario, que o parser de YAML descarta."""
    for n, linha in enumerate(texto.splitlines(), 1):
        if "#" in linha and URL_COM_CREDENCIAL.search(linha.split("#", 1)[1]):
            add("3.3", Obj(arquivo, {"kind": "linha", "metadata": {"name": str(n)}}),
                "credencial em comentario")


# --- Trivy -----------------------------------------------------------------------

def trivy(alvos, add):
    """Roda o Trivy com todas as severidades: o catalogo classifica como LOW
    regras que o padrao trata como obrigatorias (2.1, partes da 3.2)."""
    if not shutil.which("trivy"):
        return False
    cmd = ["trivy", "config", "--quiet", "--format", "json",
           "--severity", "LOW,MEDIUM,HIGH,CRITICAL",
           "--config-data", str(TRIVY_DATA), "--ignorefile", str(TRIVY_IGNORE)]
    for alvo in alvos:
        r = subprocess.run(cmd + [alvo], capture_output=True, text=True)
        if r.returncode != 0:
            print("trivy falhou em {}: {}".format(alvo, r.stderr.strip()[:300]), file=sys.stderr)
            return False
        base = pathlib.Path(alvo)
        for res in json.loads(r.stdout or "{}").get("Results") or []:
            arq = str(base / res["Target"]) if base.is_dir() else alvo
            for m in res.get("Misconfigurations") or []:
                regra = KSV_PARA_REGRA.get(m["ID"], "?")
                add(regra, Obj(arq, {"kind": "", "metadata": {"name": ""}}),
                    "{} ({}): {}{}".format(m["ID"], m["Severity"], m["Message"],
                                           " [alem do texto da 3.2]" if m["ID"] in ALEM_DO_PADRAO else ""),
                    origem="trivy", aviso=(regra == "?" or m["ID"] in ALEM_DO_PADRAO))
    return True


# --- execucao ----------------------------------------------------------------------

def uso(msg):
    """Erro de uso sai com 2, para nao se confundir com manifesto reprovado (1)."""
    print("confere.py: " + msg, file=sys.stderr)
    sys.exit(2)


def carrega(alvos):
    objs, textos = [], []
    for alvo in alvos:
        p = pathlib.Path(alvo)
        if not p.exists():
            uso("caminho inexistente: {}".format(alvo))
        arquivos = sorted(x for x in p.rglob("*") if x.suffix in (".yaml", ".yml")) \
            if p.is_dir() else [p]
        for arq in arquivos:
            texto = arq.read_text(encoding="utf-8")
            textos.append((str(arq), texto))
            try:
                docs = list(yaml.safe_load_all(texto))
            except yaml.YAMLError as e:
                uso("YAML invalido em {}: {}".format(arq, e))
            objs += [Obj(str(arq), d) for d in docs if isinstance(d, dict) and d.get("kind")]
    return objs, textos


def indexa(objs):
    idx = {"pods": {}, "pdbs": {}, "sa": {}, "uso_sa": {}}
    for o in objs:
        if o.kind in COM_POD:
            spec = pod_spec(o.raw)
            idx["pods"].setdefault(o.namespace, []).append({
                "rotulo": o.rotulo, "labels": rotulos_do_pod(o.raw), "portas": portas(spec),
                "replicas": (o.raw.get("spec") or {}).get("replicas", 1)})
            sa = spec.get("serviceAccountName") or spec.get("serviceAccount") or "default"
            idx["uso_sa"].setdefault((o.namespace, sa), set()).add(o.rotulo)
        elif o.kind == "PodDisruptionBudget":
            sel = ((o.raw.get("spec") or {}).get("selector") or {}).get("matchLabels") or {}
            idx["pdbs"].setdefault(o.namespace, []).append(sel)
        elif o.kind == "ServiceAccount":
            idx["sa"][(o.namespace, o.nome)] = o.raw.get("automountServiceAccountToken")
    return idx


def confere(alvos, usar_trivy=True):
    achados = []

    def add(regra, o, msg, origem="script", aviso=False):
        achados.append(Achado(regra, o.arquivo, o.rotulo, msg, origem, aviso))

    objs, textos = carrega(alvos)
    idx = indexa(objs)
    for arq, texto in textos:
        comentarios(arq, texto, add)
    for o in objs:
        bloco1(o, add)
        if o.kind in COM_POD:
            seletor_do_workload(o, add)
            bloco2(o, idx, add)
            bloco3(o, idx, add)
        elif o.kind == "Service":
            seletor_do_service(o, idx, add)
        elif o.kind == "PodDisruptionBudget":
            seletor_do_pdb(o, idx, add)
        elif o.kind in ("ConfigMap", "Secret"):
            configmap_e_secret(o, add)
    rodou = trivy(alvos, add) if usar_trivy else False
    return achados, objs, rodou


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("alvos", nargs="+")
    ap.add_argument("--sem-trivy", action="store_true")
    args = ap.parse_args(argv)

    achados, objs, rodou = confere(args.alvos, not args.sem_trivy)
    chave = lambda a: (a.nivel != "ERRO", [int(x) for x in a.regra.split(".")]  # noqa: E731
                       if a.regra != "?" else [9], a.arquivo, a.origem)
    for a in sorted(achados, key=chave):
        print("{:<5} {:<4} [{:<6}] {} {} — {}".format(
            a.nivel, a.regra, a.origem, a.arquivo, a.objeto, a.msg))
    erros = sum(a.nivel == "ERRO" for a in achados)
    regras = sorted({a.regra for a in achados if a.nivel == "ERRO"},
                    key=lambda r: [int(x) for x in r.split(".")] if r != "?" else [9])
    print("\n{} objeto(s): {} erro(s), {} aviso(s). Regras violadas: {}".format(
        len(objs), erros, len(achados) - erros, ", ".join(regras) or "nenhuma"))
    if not rodou and not args.sem_trivy:
        print("NAO VERIFICADO: Trivy indisponivel — regras {} ficaram sem conferencia.".format(
            ", ".join(REGRAS_DO_TRIVY)))
    print("Falta a parte que exige ler o projeto: ver 'Conferencia — o que o script nao "
          "decide' no SKILL.md.")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
