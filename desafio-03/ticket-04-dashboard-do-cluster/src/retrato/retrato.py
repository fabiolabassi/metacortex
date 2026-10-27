"""Objetos da API -> linhas de tela (TRD §4). Funcoes puras sobre os modelos
do cliente oficial; campo ausente vira zero/vazio, nunca erro (RNF-05)."""
import datetime
import logging
from concurrent.futures import ThreadPoolExecutor

from retrato.leitura import FalhaDeLeitura

log = logging.getLogger("retrato")
LIMITE_EVENTOS = 100


def _agora():
    return datetime.datetime.now(datetime.timezone.utc)


def _idade(ts, agora=None):
    if not ts:
        return None
    seg = int(((agora or _agora()) - ts).total_seconds())
    for unidade, tam in (("d", 86400), ("h", 3600), ("m", 60)):
        if seg >= tam:
            return "{}{}".format(seg // tam, unidade)
    return "{}s".format(max(seg, 0))


def _sem_readiness(containers):
    return any(c.readiness_probe is None for c in containers or [])


# --- pods ------------------------------------------------------------------------

def linha_pod(p):
    st, spec = p.status, p.spec
    statuses = (st.container_statuses or []) if st else []
    containers = spec.containers if spec else []
    estado = (st.phase if st else None) or "Unknown"
    motivo = None
    if st and st.reason:  # Evicted, NodeLost...
        estado, motivo = st.reason, st.message
    else:
        for cs in statuses:
            s = cs.state
            if s and s.waiting and s.waiting.reason and s.waiting.reason != "ContainerCreating":
                estado, motivo = s.waiting.reason, s.waiting.message
                break
            if s and s.terminated and s.terminated.reason not in (None, "Completed"):
                estado, motivo = s.terminated.reason, s.terminated.message
                break
        else:
            for cond in (st.conditions or []) if st else []:
                if cond.type == "PodScheduled" and cond.status == "False":
                    estado, motivo = cond.reason or "Unschedulable", cond.message
                    break
            else:
                for cs in statuses:
                    if cs.state and cs.state.waiting and cs.state.waiting.reason:
                        estado = cs.state.waiting.reason
    ultimo = None
    for cs in statuses:
        t = cs.last_state.terminated if cs.last_state else None
        if t:
            ultimo = "{} ({})".format(t.reason or "Terminated", t.exit_code)
            break
    return {
        "nome": p.metadata.name,
        "estado": estado,
        "falha": estado not in ("Running", "Succeeded", "Pending") or bool(ultimo and "OOM" in ultimo),
        "motivo": motivo,
        "ultimo_termino": ultimo,
        "prontos": "{}/{}".format(sum(1 for cs in statuses if cs.ready), len(containers or [])),
        "reinicios": sum(cs.restart_count or 0 for cs in statuses),
        "no": spec.node_name if spec else None,
        "idade": _idade(p.metadata.creation_timestamp),
        # So faz sentido em pod rodando: pod de Job que terminou nao recebe trafego.
        "sem_readiness": estado == "Running" and _sem_readiness(containers),
    }


# --- deployments -----------------------------------------------------------------

def linha_deployment(d):
    st = d.status
    desejadas = d.spec.replicas if d.spec.replicas is not None else 1
    prontas = (st.ready_replicas if st else None) or 0  # ausente quando nenhuma esta pronta
    condicao = None
    for c in (st.conditions or []) if st else []:
        if c.type in ("Available", "Progressing") and c.status == "False":
            condicao = c.reason
            break
    containers = d.spec.template.spec.containers if d.spec.template and d.spec.template.spec else []
    return {
        "nome": d.metadata.name,
        "prontas": prontas,
        "desejadas": desejadas,
        "atualizadas": (st.updated_replicas if st else None) or 0,
        "falha": prontas < desejadas,
        "condicao": condicao,
        "imagens": [c.image for c in containers],
        "idade": _idade(d.metadata.creation_timestamp),
        "sem_readiness": _sem_readiness(containers),
    }


# --- services --------------------------------------------------------------------

def _casa(seletor, rotulos):
    return bool(seletor) and all((rotulos or {}).get(k) == v for k, v in seletor.items())


def linha_service(s, slices, pods, erro_slices=None):
    spec = s.spec
    portas = ["{}→{}".format(p.port, p.target_port if p.target_port is not None else p.port)
              for p in spec.ports or []]
    base = {"nome": s.metadata.name, "tipo": spec.type, "portas": portas, "dica": None}
    if spec.type == "ExternalName":
        return dict(base, endpoint="ExternalName", falha=False)
    if erro_slices:
        return dict(base, endpoint="sem permissão" if erro_slices["tipo"] == "sem_permissao"
                    else "indisponível", falha=False, erro_endpoint=erro_slices)
    meus = [sl for sl in slices
            if (sl.metadata.labels or {}).get("kubernetes.io/service-name") == s.metadata.name]
    enderecos = [e for sl in meus for e in (sl.endpoints or [])]  # endpoints ausente = nenhum
    # ready nulo deve ser lido como pronto (discovery.k8s.io/v1).
    prontos = sum(1 for e in enderecos if not e.conditions or e.conditions.ready is not False)
    porta_ok = any(sl.ports for sl in meus)
    if not spec.selector:
        return dict(base, endpoint="sem seletor ({} manuais)".format(len(enderecos)),
                    falha=not enderecos)
    if not enderecos:
        casam = sum(1 for p in pods if _casa(spec.selector, p.metadata.labels))
        seletor = ", ".join("{}={}".format(k, v) for k, v in sorted(spec.selector.items()))
        dica = ("nenhum pod do namespace casa com o seletor {}".format(seletor) if not casam
                else "{} pod(s) casam com o seletor, nenhum virou endpoint".format(casam))
        return dict(base, endpoint="sem endpoint", falha=True, dica=dica)
    if not porta_ok:
        return dict(base, endpoint="porta não resolvida", falha=True,
                    dica="targetPort não existe em nenhum container selecionado")
    return dict(base, endpoint="{}/{} prontos".format(prontos, len(enderecos)), falha=prontos == 0)


# --- eventos ---------------------------------------------------------------------

def _quando(ev):
    return (ev.last_timestamp or ev.event_time or ev.first_timestamp
            or ev.metadata.creation_timestamp)


def linhas_eventos(eventos):
    ordenados = sorted(eventos, key=lambda e: (_quando(e) or datetime.datetime.min.replace(
        tzinfo=datetime.timezone.utc), e.type == "Warning"), reverse=True)
    out = []
    for ev in ordenados[:LIMITE_EVENTOS]:
        obj = ev.involved_object
        out.append({
            "tipo": ev.type, "motivo": ev.reason,
            "objeto": "{}/{}".format(obj.kind, obj.name) if obj else None,
            "mensagem": ev.message, "contagem": ev.count or (ev.series.count if ev.series else 1),
            "idade": _idade(_quando(ev)), "falha": ev.type == "Warning",
        })
    return out


# --- montagem --------------------------------------------------------------------

def _resultado(futuro):
    try:
        return futuro.result(), None
    except FalhaDeLeitura as e:
        return None, e.como_dict()
    except Exception as e:  # noqa: BLE001 — vira erro da secao, nunca traceback
        log.error("erro interno ao listar: %s", type(e).__name__)
        return None, {"tipo": "interno", "mensagem": "Erro interno ao montar a seção."}


def _secao(funcao, *args):
    try:
        return {"itens": funcao(*args)}
    except Exception as e:  # noqa: BLE001
        log.error("erro interno ao montar secao: %s", type(e).__name__)
        return {"erro": {"tipo": "interno", "mensagem": "Erro interno ao montar a seção."}}


def monta(cluster, ns):
    """Cinco listagens em paralelo; cada secao e {itens} ou {erro} (design, decisao 2)."""
    with ThreadPoolExecutor(max_workers=5) as ex:
        fut = {nome: ex.submit(getattr(cluster, "lista_" + nome), ns)
               for nome in ("pods", "deployments", "services", "endpointslices", "eventos")}
    r = {nome: _resultado(f) for nome, f in fut.items()}
    pods, erro_pods = r["pods"]
    out = {"namespace": ns, "gerado_em": _agora().strftime("%Y-%m-%dT%H:%M:%SZ")}
    out["pods"] = {"erro": erro_pods} if erro_pods else _secao(lambda: [linha_pod(p) for p in pods])
    deps, erro = r["deployments"]
    out["deployments"] = {"erro": erro} if erro else _secao(lambda: [linha_deployment(d) for d in deps])
    svcs, erro = r["services"]
    slices, erro_sl = r["endpointslices"]
    out["services"] = {"erro": erro} if erro else _secao(
        lambda: [linha_service(s, slices or [], pods or [], erro_sl) for s in svcs])
    evs, erro = r["eventos"]
    out["eventos"] = {"erro": erro} if erro else _secao(linhas_eventos, evs)
    return out
