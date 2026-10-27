"""Conexao com o host: uma sessao do OpenSSH do sistema (ADR-0001).

A linha de comando do ssh nunca e impressa, e o stderr do ssh nunca e
repassado cru: ele pode trazer o caminho da chave (RNF-03)."""
import importlib.resources
import os
import re
import subprocess

from roster_audit.erros import ErroDeUso, HostInalcancavel

# TRD §6: padrao no stderr do ssh -> mensagem. A ordem importa: a primeira que casar vale.
FALHAS = (
    (r"Could not resolve hostname", "não foi possível resolver o endereço {endereco}"),
    (r"Connection refused", "{endereco}:{porta} recusou a conexão; o SSH está fora do ar ou a porta está errada"),
    (r"timed out|No route to host|Network is unreachable|Operation timed out",
     "{endereco}:{porta} não respondeu em {timeout}s"),
    (r"UNPROTECTED PRIVATE KEY|bad permissions",
     "a chave privada tem permissão aberta demais (precisa ser 600)"),
    (r"REMOTE HOST IDENTIFICATION HAS CHANGED",
     "a chave do host {endereco} MUDOU em relação ao known_hosts; possível interceptação, verifique antes de prosseguir"),
    (r"Host key verification failed|No .* host key is known",
     "a chave do host {endereco} não está no known_hosts; use --aceitar-host-novo se o host for novo"),
    (r"Permission denied", "o host recusou a chave para o usuário {usuario}"),
    (r"invalid format|error in libcrypto|incorrect passphrase|Load key",
     "a chave privada não pode ser usada (formato inválido ou protegida por senha sem ssh-agent)"),
    (r"Connection closed|Connection reset|kex_exchange_identification",
     "{endereco}:{porta} encerrou a conexão antes da autenticação"),
)


def script_de_coleta():
    return importlib.resources.files("roster_audit").joinpath("coleta.sh").read_text(encoding="utf-8")


def verifica_chave(chave):
    if not chave or not os.path.isfile(chave) or not os.access(chave, os.R_OK):
        # O caminho nao entra na mensagem (RNF-03).
        raise ErroDeUso("a chave privada informada em --chave não existe ou não pode ser lida")


def comando_ssh(endereco, porta, usuario, chave, timeout, aceitar_host_novo):
    return [
        "ssh", "-T",
        "-o", "BatchMode=yes",
        "-o", "IdentitiesOnly=yes",
        "-o", "ConnectTimeout={}".format(timeout),
        "-o", "StrictHostKeyChecking={}".format("accept-new" if aceitar_host_novo else "yes"),
        "-o", "LogLevel=ERROR",
        "-i", chave,
        "-p", str(porta),
        "-l", usuario,
        "--", endereco, "/bin/sh -s",
    ]


def classifica(stderr, **ctx):
    for padrao, msg in FALHAS:
        if re.search(padrao, stderr):
            return msg.format(**ctx)
    return "falha de SSH não classificada ao conectar em {endereco}:{porta}".format(**ctx)


def coleta(endereco, porta, usuario, chave, timeout=10, aceitar_host_novo=False, sudo=False,
           timeout_total=60):
    """Roda a coleta e devolve o stdout (texto com as secoes ##RA##)."""
    verifica_chave(chave)
    cmd = comando_ssh(endereco, porta, usuario, chave, timeout, aceitar_host_novo)
    entrada = "RA_SUDO={}\n{}".format(1 if sudo else 0, script_de_coleta())
    ctx = {"endereco": endereco, "porta": porta, "usuario": usuario, "timeout": timeout}
    try:
        r = subprocess.run(cmd, input=entrada, capture_output=True, text=True,
                           timeout=timeout_total)
    except FileNotFoundError:
        raise ErroDeUso("cliente ssh não encontrado no PATH")
    except subprocess.TimeoutExpired:
        raise HostInalcancavel("{endereco}:{porta} não terminou a coleta em {t}s".format(
            t=timeout_total, **ctx))
    if r.returncode == 255 or "##RA## hostname" not in r.stdout:
        raise HostInalcancavel(classifica(r.stderr, **ctx))
    return r.stdout
