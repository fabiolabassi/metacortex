"""roster-audit: audita uma VM por SSH e compara com o baseline do parque.

Codigos de saida (TRD §5):
  0  todas as regras conformes
  1  pelo menos um desvio
  2  sem desvio, mas com regra nao verificada
  3  erro de uso (argumento, baseline ou chave)
  4  host inalcancavel ou autenticacao recusada
"""
import argparse
import datetime
import sys

from roster_audit import __version__, baseline, conexao, parser, regras, saida
from roster_audit.erros import RosterAuditError


class Argumentos(argparse.ArgumentParser):
    def error(self, message):
        # argparse sai com 2 por padrao, que aqui significa "incompleto". Uso errado e 3.
        self.print_usage(sys.stderr)
        print("roster-audit: erro: {}".format(message), file=sys.stderr)
        sys.exit(3)


def argumentos(argv):
    ap = Argumentos(prog="roster-audit", description=__doc__.split("\n")[0],
                    epilog=__doc__.split("\n", 2)[2], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--endereco", required=True, help="IP ou nome da VM")
    ap.add_argument("--porta", type=int, default=22)
    ap.add_argument("--usuario", required=True)
    ap.add_argument("--chave", required=True, help="caminho da chave privada (nunca é exibido)")
    ap.add_argument("--baseline", help="baseline.yaml (padrão: o embutido, v1)")
    ap.add_argument("--formato", choices=("markdown", "json"), default="markdown")
    ap.add_argument("--sudo", action="store_true",
                    help="tenta sudo -n (nunca pede senha) para os dados que exigem privilégio")
    ap.add_argument("--aceitar-host-novo", action="store_true",
                    help="aceita chave de host ainda desconhecida (nunca uma chave divergente)")
    ap.add_argument("--timeout", type=int, default=10, help="segundos para conectar (padrão 10)")
    ap.add_argument("--debug", action="store_true", help="mostra o traceback de erros inesperados")
    ap.add_argument("--version", action="version", version="%(prog)s " + __version__)
    return ap.parse_args(argv)


def executa(args):
    base = baseline.carrega(args.baseline)
    coletado_em = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    bruto = conexao.coleta(args.endereco, args.porta, args.usuario, args.chave,
                           timeout=args.timeout, aceitar_host_novo=args.aceitar_host_novo,
                           sudo=args.sudo)
    host, inv, meta = parser.interpreta(bruto, args.endereco, coletado_em)
    conformidade, resumo = regras.avalia(base, inv, meta)
    res = saida.resultado(host, inv, conformidade, resumo)
    if args.formato == "json":
        print(saida.em_json(res))
    else:
        print(saida.em_markdown(res, base.get("versao")), end="")
    if resumo["desvio"]:
        return 1
    if resumo["nao_verificado"]:
        return 2
    return 0


def main(argv=None):
    args = argumentos(sys.argv[1:] if argv is None else argv)
    try:
        return executa(args)
    except RosterAuditError as e:
        print("roster-audit: erro: {}".format(e), file=sys.stderr)
        return e.codigo
    except KeyboardInterrupt:
        print("roster-audit: interrompido", file=sys.stderr)
        return 4
    except Exception:  # noqa: BLE001 — nada de traceback para o operador (RF-07)
        if args.debug:
            raise
        print("roster-audit: erro: falha inesperada; rode de novo com --debug para detalhes",
              file=sys.stderr)
        return 4
