"""Erros com codigo de saida proprio (TRD §5). Mensagem sempre sem segredo."""


class RosterAuditError(Exception):
    codigo = 4


class ErroDeUso(RosterAuditError):
    codigo = 3


class HostInalcancavel(RosterAuditError):
    codigo = 4
