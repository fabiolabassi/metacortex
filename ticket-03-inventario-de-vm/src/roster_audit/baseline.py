"""Carga e validacao do baseline.yaml."""
import importlib.resources

import yaml

from roster_audit.erros import ErroDeUso

REGRAS = (
    "so.distribuicao", "so.versao_minima", "kernel.versao_minima",
    "servicos.ativos", "servicos.proibidos", "swap.habilitado",
    "portas_em_escuta.publicas_permitidas", "portas_em_escuta.somente_rede_interna",
    "chaves_ssh.emitidas_por", "ssh.login_de_root", "ntp.sincronizado",
)
SEVERIDADES = ("critico", "alto", "medio")


def carrega(caminho=None):
    try:
        if caminho:
            with open(caminho, encoding="utf-8") as f:
                dados = yaml.safe_load(f)
        else:
            texto = importlib.resources.files("roster_audit").joinpath(
                "baseline_padrao.yaml").read_text(encoding="utf-8")
            dados = yaml.safe_load(texto)
    except OSError as e:
        raise ErroDeUso("não foi possível ler o baseline: {}".format(e.strerror))
    except yaml.YAMLError:
        raise ErroDeUso("baseline não é um YAML válido")
    return valida(dados)


def valida(dados):
    if not isinstance(dados, dict) or not isinstance(dados.get("esperado"), dict):
        raise ErroDeUso("baseline sem a chave 'esperado'")
    sev = {}
    for nivel, regras in (dados.get("severidade") or {}).items():
        if nivel not in SEVERIDADES:
            raise ErroDeUso("severidade desconhecida no baseline: {}".format(nivel))
        for r in regras or []:
            sev[r] = nivel
    for regra in REGRAS:
        if esperado(dados, regra) is None:
            raise ErroDeUso("baseline sem valor esperado para {}".format(regra))
        if regra not in sev:
            raise ErroDeUso("baseline sem severidade para {}".format(regra))
    dados["_severidade"] = sev
    return dados


def esperado(dados, regra):
    grupo, campo = regra.split(".", 1)
    return (dados["esperado"].get(grupo) or {}).get(campo)
