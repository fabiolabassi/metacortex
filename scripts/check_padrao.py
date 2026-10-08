#!/usr/bin/env python3
"""Verificador do Padrao de Manifests da Metacortex (revisao 2026-07-29).

Cobre o que a varredura do Trivy nao conhece: nomenclatura, rotulos,
coerencia entre seletores, regras por ambiente, registry interno, segredo em
comentario e o processo de excecao. Uso:

    python3 scripts/check_padrao.py [--github] [CAMINHO ...]

Nivel de cada achado, na mesma linguagem do wiki:
    ERRO   regra obrigatoria ou proibida — sai com codigo 1
    AVISO  regra recomendada — nao reprova, mas a excecao vai escrita no PR

Excecao a regra obrigatoria (secao "Exceções" do wiki) e declarada no proprio
objeto, para ficar versionada junto com o que ela libera:

    metadata:
      annotations:
        excecao.metacortex.io/2.3: "validade=2026-12-31; aprovacao=<link do PR>"

Com aprovacao e validade futura, o ERRO vira AVISO. Vencida ou sem aprovacao,
continua ERRO. Regra proibida nao aceita excecao para workload de cliente.
"""
import argparse
import datetime
import pathlib
import re
import sys

import yaml

# --- constantes do padrao ---------------------------------------------------

# 1.1 — minusculo, palavras separadas por um hifen, sem _ e sem ponto.
KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# 1.2
AMBIENTES = ("dev", "stg", "prod")
NAMESPACE = re.compile(r"^(?P<cliente>[a-z0-9]+(?:-[a-z0-9]+)*)-(?P<amb>dev|stg|prod)$")
# 1.3
ROTULOS = (
    "app.kubernetes.io/name",
    "app.kubernetes.io/instance",
    "app.kubernetes.io/part-of",
    "app.kubernetes.io/managed-by",
)
MANAGED_BY = ("platform", "argocd", "helm")
# 1.6
NOMES_GENERICOS = {"app", "main", "container"}
# 3.7
REGISTRY = "registry.metacortex.io/"
# 3.3 — heuristicas de valor sensivel
CHAVE_SENSIVEL = re.compile(
    r"(passw|senha|secret|token|api[-_]?key|credential|private[-_]?key|dsn)", re.I)
URL_COM_CREDENCIAL = re.compile(r"[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@", re.I)

COM_POD = {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet", "Job", "CronJob", "Pod"}
LONGA_DURACAO = {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet", "Pod"}
SEM_NAMESPACE = {"Namespace", "ClusterRole", "ClusterRoleBinding", "PersistentVolume",
                 "StorageClass", "CustomResourceDefinition", "PriorityClass"}

# Campos de SecurityContext que nao existem em PodSecurityContext: o apiserver
# recusa o manifesto inteiro se aparecerem em spec.securityContext.
SO_NO_CONTAINER = ("allowPrivilegeEscalation", "readOnlyRootFilesystem",
                   "capabilities", "privileged", "procMount")

PROIBIDAS = {"3.1", "3.3", "3.6"}
RECOMENDADAS = {"1.5", "1.6", "2.5", "2.6", "3.5"}


# --- achados ----------------------------------------------------------------

class Relatorio:
    def __init__(self, hoje):
        self.hoje = hoje
        self.achados = []  # (nivel, regra, arquivo, objeto, mensagem)

    def registra(self, ctx, regra, msg, aviso=False):
        """aviso=True: ponto que o padrao ainda nao exige, mas o cluster cobra."""
        nivel = "AVISO" if aviso or regra in RECOMENDADAS else "ERRO"
        if nivel == "ERRO":
            nivel, msg = self._aplica_excecao(ctx, regra, msg)
        self.achados.append((nivel, regra, ctx.arquivo, ctx.rotulo, msg))

    def _aplica_excecao(self, ctx, regra, msg):
        texto = ctx.anotacoes.get("excecao.metacortex.io/" + regra)
        if texto is None:
            return "ERRO", msg
        if regra in PROIBIDAS:
            return "ERRO", msg + " (regra proibida nao aceita excecao)"
        campos = dict(p.strip().split("=", 1) for p in texto.split(";") if "=" in p)
        if not campos.get("aprovacao"):
            return "ERRO", msg + " (excecao sem aprovacao de Seguranca & Compliance)"
        try:
            validade = datetime.date.fromisoformat(campos.get("validade", ""))
        except ValueError:
            return "ERRO", msg + " (excecao sem validade AAAA-MM-DD)"
        if validade < self.hoje:
            return "ERRO", msg + " (excecao vencida em {})".format(validade)
        return "AVISO", msg + " (excecao valida ate {}, {})".format(validade, campos["aprovacao"])

    def erros(self):
        return [a for a in self.achados if a[0] == "ERRO"]


class Ctx:
    """Onde um achado aconteceu: arquivo, objeto e as anotacoes de excecao."""

    def __init__(self, arquivo, obj):
        md = obj.get("metadata") or {}
        self.arquivo = arquivo
        self.obj = obj
        self.kind = obj.get("kind")
        self.nome = md.get("name", "")
        self.namespace = md.get("namespace")
        self.anotacoes = md.get("annotations") or {}
        self.rotulo = "{}/{}".format(self.kind, self.nome)


# --- utilitarios ------------------------------------------------------------

def ambiente(ns):
    m = NAMESPACE.match(ns or "")
    return m.group("amb") if m else None


def cliente(ns):
    m = NAMESPACE.match(ns or "")
    return m.group("cliente") if m else None


def niveis_de_metadata(obj):
    """Todos os metadata que geram objeto no cluster: o proprio, o Job de um
    CronJob e o Pod do template."""
    yield "", obj.get("metadata") or {}
    spec = obj.get("spec") or {}
    if obj.get("kind") == "CronJob":
        jt = spec.get("jobTemplate") or {}
        yield "jobTemplate ", jt.get("metadata") or {}
        spec = jt.get("spec") or {}
    if obj.get("kind") in COM_POD - {"Pod"}:
        yield "template do pod ", (spec.get("template") or {}).get("metadata") or {}


def pod_spec(obj):
    if obj.get("kind") == "Pod":
        return obj.get("spec") or {}
    spec = obj.get("spec") or {}
    if obj.get("kind") == "CronJob":
        spec = ((spec.get("jobTemplate") or {}).get("spec")) or {}
    return (spec.get("template") or {}).get("spec") or {}


def rotulos_do_pod(obj):
    if obj.get("kind") == "Pod":
        return (obj.get("metadata") or {}).get("labels") or {}
    return list(niveis_de_metadata(obj))[-1][1].get("labels") or {}


def casa(seletor, rotulos):
    return bool(seletor) and all(rotulos.get(k) == v for k, v in seletor.items())


def containers(spec):
    for tipo in ("initContainers", "containers", "ephemeralContainers"):
        for c in spec.get(tipo) or []:
            yield tipo, c


def portas_nomeadas(spec):
    return {p.get("name") for _, c in containers(spec) for p in c.get("ports") or []
            if p.get("name")}


# --- Bloco 1 ----------------------------------------------------------------

def bloco1(rel, ctx):
    if not KEBAB.match(ctx.nome) or len(ctx.nome) > 63:
        rel.registra(ctx, "1.1", "nome '{}' fora de kebab-case".format(ctx.nome))

    ns = ctx.nome if ctx.kind == "Namespace" else ctx.namespace
    if ctx.kind not in SEM_NAMESPACE and not ns:
        rel.registra(ctx, "1.2", "sem metadata.namespace — aterrissaria no namespace do contexto")
    elif ns and not NAMESPACE.match(ns):
        rel.registra(ctx, "1.2", "namespace '{}' fora de <cliente>-<{}>".format(
            ns, "|".join(AMBIENTES)))

    for nivel, md in niveis_de_metadata(ctx.obj):
        labels = md.get("labels") or {}
        faltam = [r for r in ROTULOS if r not in labels]
        if faltam:
            rel.registra(ctx, "1.3", "{}sem {}".format(nivel, ", ".join(faltam)))
        mb = labels.get("app.kubernetes.io/managed-by")
        if mb is not None and mb not in MANAGED_BY:
            rel.registra(ctx, "1.3", "{}managed-by '{}' fora de {}".format(
                nivel, mb, "|".join(MANAGED_BY)))
        # Coerencia com o namespace: e o que faz o rateio por cliente fechar.
        inst, part = labels.get("app.kubernetes.io/instance"), labels.get("app.kubernetes.io/part-of")
        if ns and NAMESPACE.match(ns):
            if inst is not None and inst != ns:
                rel.registra(ctx, "1.3", "{}instance '{}' diferente do namespace '{}'".format(
                    nivel, inst, ns))
            if part is not None and part != cliente(ns):
                rel.registra(ctx, "1.3", "{}part-of '{}' diferente do cliente '{}'".format(
                    nivel, part, cliente(ns)))

    if not ctx.anotacoes.get("metacortex.io/owner"):
        rel.registra(ctx, "1.5", "sem anotacao metacortex.io/owner")
    if ctx.kind in COM_POD and not ctx.anotacoes.get("metacortex.io/runbook"):
        rel.registra(ctx, "1.5", "sem anotacao metacortex.io/runbook")


def seletor_do_workload(rel, ctx):
    if ctx.kind not in {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet"}:
        return
    sel = ((ctx.obj.get("spec") or {}).get("selector") or {})
    ml = sel.get("matchLabels") or {}
    if not ml and not sel.get("matchExpressions"):
        rel.registra(ctx, "1.4", "sem spec.selector")
        return
    labels = rotulos_do_pod(ctx.obj)
    for k, v in ml.items():
        if labels.get(k) != v:
            rel.registra(ctx, "1.4", "matchLabels {}={} nao casa com o pod ({})".format(
                k, v, labels.get(k, "ausente")))


def seletor_do_service(rel, ctx, indice):
    spec = ctx.obj.get("spec") or {}
    if spec.get("type") == "ExternalName":
        return
    sel = spec.get("selector") or {}
    if not sel:
        rel.registra(ctx, "1.4", "Service sem seletor — so faz sentido com Endpoints manuais")
        return
    alvos = [w for w in indice["pods"].get(ctx.namespace, []) if casa(sel, w["labels"])]
    if not alvos:
        rel.registra(ctx, "1.4", "nenhum pod do namespace casa com o seletor {} — o Service "
                                 "subiria sem endpoint".format(sel))
        return
    # 4.5 — targetPort por nome que nenhum container declara tambem deixa o
    # Service sem endpoint, e da mesma forma silenciosa.
    for p in spec.get("ports") or []:
        tp = p.get("targetPort")
        if isinstance(tp, str) and not tp.isdigit():
            if not any(tp in w["portas"] for w in alvos):
                rel.registra(ctx, "1.4", "targetPort '{}' nao existe em nenhum container "
                                         "selecionado".format(tp))


def seletor_do_pdb(rel, ctx, indice):
    sel = ((ctx.obj.get("spec") or {}).get("selector") or {}).get("matchLabels") or {}
    alvos = [w for w in indice["pods"].get(ctx.namespace, []) if casa(sel, w["labels"])]
    if not alvos:
        rel.registra(ctx, "1.4", "PDB nao seleciona nenhum pod — protege nada, em silencio")
        return
    mina = (ctx.obj.get("spec") or {}).get("minAvailable")
    for w in alvos:
        if isinstance(mina, int) and mina >= w["replicas"]:
            rel.registra(ctx, "2.5", "minAvailable={} com {} replicas trava o drain do no".format(
                mina, w["replicas"]))


# --- Bloco 2 ----------------------------------------------------------------

def bloco2(rel, ctx, indice):
    spec = pod_spec(ctx.obj)
    portas = portas_nomeadas(spec)
    for tipo, c in containers(spec):
        alvo = "{} '{}'".format(tipo[:-1], c.get("name"))
        res = c.get("resources") or {}
        for campo in ("requests", "limits"):
            for r in ("cpu", "memory"):
                if r not in (res.get(campo) or {}):
                    rel.registra(ctx, "2.1", "{} sem {}.{}".format(alvo, campo, r))
        if tipo != "containers":
            continue
        for probe in ("readinessProbe", "livenessProbe"):
            p = c.get(probe)
            if not p:
                rel.registra(ctx, "2.2", "{} sem {}".format(alvo, probe))
                continue
            porta = (p.get("httpGet") or p.get("tcpSocket") or p.get("grpc") or {}).get("port")
            if isinstance(porta, str) and porta not in portas:
                rel.registra(ctx, "2.2", "{} {} aponta para a porta '{}', que o container "
                                         "nao declara".format(alvo, probe, porta))
        r, l = c.get("readinessProbe"), c.get("livenessProbe")
        if r and l and r == l:
            rel.registra(ctx, "2.2", "{} com readiness e liveness identicas — se a checagem "
                                     "inclui o banco, banco lento reinicia o pod".format(alvo))

    if ambiente(ctx.namespace) != "prod" or ctx.kind not in {"Deployment", "StatefulSet"}:
        return
    s = ctx.obj.get("spec") or {}
    replicas = s.get("replicas", 1)
    if replicas < 2:
        rel.registra(ctx, "2.3", "replicas={} em prod".format(replicas))
    if ctx.kind == "Deployment":
        st = s.get("strategy") or {}
        ru = st.get("rollingUpdate") or {}
        if st.get("type", "RollingUpdate") != "RollingUpdate" or \
                str(ru.get("maxUnavailable", "25%")) != "0" or \
                str(ru.get("maxSurge", "25%")) in ("0", "0%"):
            rel.registra(ctx, "2.4", "prod exige RollingUpdate com maxUnavailable: 0 e maxSurge: 1")
    if replicas >= 2:
        labels = rotulos_do_pod(ctx.obj)
        if not any(casa(sel, labels) for sel in indice["pdbs"].get(ctx.namespace, [])):
            rel.registra(ctx, "2.5", "{} replicas em prod sem PodDisruptionBudget".format(replicas))


# --- Bloco 3 ----------------------------------------------------------------

def bloco3(rel, ctx, indice):
    spec = pod_spec(ctx.obj)
    pod_sc = spec.get("securityContext") or {}

    for campo in ("hostNetwork", "hostPID", "hostIPC"):
        if spec.get(campo) is True:
            rel.registra(ctx, "3.6", "{}: true".format(campo))

    errados = [c for c in SO_NO_CONTAINER if c in pod_sc]
    if errados:
        rel.registra(ctx, "3.2", "{} em spec.securityContext — so existem no container; "
                                 "o apiserver recusa".format(", ".join(errados)))
    if (pod_sc.get("seccompProfile") or {}).get("type") not in ("RuntimeDefault", "Localhost"):
        rel.registra(ctx, "3.2", "sem seccompProfile RuntimeDefault — fora do texto da 3.2, "
                                 "mas Pod Security 'restricted' recusa o pod", aviso=True)

    sa = spec.get("serviceAccountName") or spec.get("serviceAccount")
    if not sa or sa == "default":
        rel.registra(ctx, "3.5", "usa a ServiceAccount default do namespace")
    elif len(indice["uso_sa"].get((ctx.namespace, sa), ())) > 1:
        rel.registra(ctx, "3.5", "ServiceAccount '{}' compartilhada com {}".format(
            sa, ", ".join(sorted(indice["uso_sa"][(ctx.namespace, sa)] - {ctx.rotulo}))))
    automount = spec.get("automountServiceAccountToken")
    if automount is None:
        automount = indice["sa"].get((ctx.namespace, sa or "default"))
    if automount is not False:
        rel.registra(ctx, "3.4", "automountServiceAccountToken nao e false (nem no pod, nem na SA)")

    for tipo, c in containers(spec):
        alvo = "{} '{}'".format(tipo[:-1], c.get("name"))
        if tipo == "containers" and c.get("name") in NOMES_GENERICOS:
            rel.registra(ctx, "1.6", "{}: nome generico, use o do componente".format(alvo))

        img = c.get("image", "")
        if not img.startswith(REGISTRY):
            rel.registra(ctx, "3.7", "{} com imagem fora de {}: {}".format(alvo, REGISTRY, img))
        if "@sha256:" not in img:
            ultimo = img.rsplit("/", 1)[-1]
            tag = ultimo.rsplit(":", 1)[1] if ":" in ultimo else None
            if tag in (None, "latest"):
                rel.registra(ctx, "3.1", "{} com {}".format(
                    alvo, "tag :latest" if tag else "imagem sem tag (equivale a :latest)"))

        sc = c.get("securityContext") or {}
        efetivo = lambda k: sc.get(k, pod_sc.get(k))  # noqa: E731 — container sobrepoe pod
        if efetivo("runAsNonRoot") is not True:
            rel.registra(ctx, "3.2", "{} sem runAsNonRoot: true".format(alvo))
        if efetivo("runAsUser") in (None, 0):
            rel.registra(ctx, "3.2", "{} sem runAsUser nao-root".format(alvo))
        if sc.get("allowPrivilegeEscalation") is not False:
            rel.registra(ctx, "3.2", "{} sem allowPrivilegeEscalation: false".format(alvo))
        if sc.get("readOnlyRootFilesystem") is not True:
            rel.registra(ctx, "3.2", "{} sem readOnlyRootFilesystem: true".format(alvo))
        if "ALL" not in ((sc.get("capabilities") or {}).get("drop") or []):
            rel.registra(ctx, "3.2", "{} sem capabilities.drop: [ALL]".format(alvo))
        if sc.get("privileged") is True:
            rel.registra(ctx, "3.6", "{} com privileged: true".format(alvo))

        for e in c.get("env") or []:
            if "value" in e and (CHAVE_SENSIVEL.search(e.get("name", ""))
                                 or URL_COM_CREDENCIAL.search(str(e["value"]))):
                rel.registra(ctx, "3.3", "{} env {} em texto puro — use secretKeyRef".format(
                    alvo, e.get("name")))


def configmap_e_secret(rel, ctx):
    if ctx.kind == "Secret":
        if ctx.obj.get("data") or ctx.obj.get("stringData"):
            rel.registra(ctx, "3.3", "Secret com valor versionado no Git — crie fora do repo")
        return
    for k, v in (ctx.obj.get("data") or {}).items():
        if CHAVE_SENSIVEL.search(k) or URL_COM_CREDENCIAL.search(str(v)):
            rel.registra(ctx, "3.3", "chave '{}' parece sensivel — ConfigMap nao guarda "
                                     "segredo".format(k))


def texto_cru(rel, arquivo, texto):
    """3.3 vale tambem para comentario, que o parser de YAML descarta."""
    for n, linha in enumerate(texto.splitlines(), 1):
        if "#" in linha and URL_COM_CREDENCIAL.search(linha.split("#", 1)[1]):
            falso = Ctx(arquivo, {"kind": "Arquivo", "metadata": {"name": "linha {}".format(n)}})
            rel.registra(falso, "3.3", "credencial em comentario")


# --- execucao ---------------------------------------------------------------

def carrega(alvos):
    docs, textos = [], []
    for alvo in alvos:
        p = pathlib.Path(alvo)
        arquivos = sorted(x for x in p.rglob("*") if x.suffix in (".yaml", ".yml")) \
            if p.is_dir() else [p]
        for arq in arquivos:
            texto = arq.read_text(encoding="utf-8")
            textos.append((str(arq), texto))
            for obj in yaml.safe_load_all(texto):
                if isinstance(obj, dict) and obj.get("kind"):
                    docs.append(Ctx(str(arq), obj))
    return docs, textos


def indexa(docs):
    indice = {"pods": {}, "pdbs": {}, "sa": {}, "uso_sa": {}}
    for ctx in docs:
        if ctx.kind in COM_POD:
            spec = pod_spec(ctx.obj)
            indice["pods"].setdefault(ctx.namespace, []).append({
                "labels": rotulos_do_pod(ctx.obj),
                "portas": portas_nomeadas(spec),
                "replicas": (ctx.obj.get("spec") or {}).get("replicas", 1),
            })
            sa = spec.get("serviceAccountName") or spec.get("serviceAccount") or "default"
            indice["uso_sa"].setdefault((ctx.namespace, sa), set()).add(ctx.rotulo)
        elif ctx.kind == "PodDisruptionBudget":
            sel = ((ctx.obj.get("spec") or {}).get("selector") or {}).get("matchLabels") or {}
            indice["pdbs"].setdefault(ctx.namespace, []).append(sel)
        elif ctx.kind == "ServiceAccount":
            indice["sa"][(ctx.namespace, ctx.nome)] = ctx.obj.get("automountServiceAccountToken")
    return indice


def verifica(alvos, hoje=None):
    rel = Relatorio(hoje or datetime.date.today())
    docs, textos = carrega(alvos)
    indice = indexa(docs)
    for arq, texto in textos:
        texto_cru(rel, arq, texto)
    for ctx in docs:
        bloco1(rel, ctx)
        if ctx.kind in COM_POD:
            seletor_do_workload(rel, ctx)
            bloco2(rel, ctx, indice)
            bloco3(rel, ctx, indice)
        elif ctx.kind == "Service":
            seletor_do_service(rel, ctx, indice)
        elif ctx.kind == "PodDisruptionBudget":
            seletor_do_pdb(rel, ctx, indice)
        elif ctx.kind in ("ConfigMap", "Secret"):
            configmap_e_secret(rel, ctx)
    return rel, len(docs)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("alvos", nargs="*", default=["manifests"])
    ap.add_argument("--github", action="store_true",
                    help="emite anotacoes ::error/::warning do GitHub Actions")
    args = ap.parse_args(argv)

    rel, n = verifica(args.alvos)
    ordem = sorted(rel.achados, key=lambda a: (a[0] != "ERRO", a[2], a[1]))
    for nivel, regra, arq, obj, msg in ordem:
        if args.github:
            cmd = "error" if nivel == "ERRO" else "warning"
            print("::{} file={},title=Padrao {}::{} — {}".format(cmd, arq, regra, obj, msg))
        else:
            print("{:<5} {:<4} {} {} — {}".format(nivel, regra, arq, obj, msg))
    print("\n{} objeto(s): {} erro(s), {} aviso(s)".format(
        n, len(rel.erros()), len(rel.achados) - len(rel.erros())))
    return 1 if rel.erros() else 0


if __name__ == "__main__":
    sys.exit(main())
