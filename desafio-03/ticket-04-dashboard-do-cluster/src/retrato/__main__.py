"""python3 -m retrato [--porta 8765] [--intervalo 10] [--kubeconfig ARQ] [--debug]"""
import argparse
import logging
import sys

from retrato import __version__
from retrato.leitura import Cluster
from retrato.servidor import servidor


def main(argv=None):
    ap = argparse.ArgumentParser(prog="retrato", description="Dashboard local, só leitura, "
                                 "do cluster do contexto corrente do kubeconfig.")
    ap.add_argument("--porta", type=int, default=8765)
    ap.add_argument("--intervalo", type=int, default=10, help="segundos entre atualizações (padrão 10)")
    ap.add_argument("--kubeconfig", help="padrão: $KUBECONFIG ou ~/.kube/config")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--version", action="version", version="%(prog)s " + __version__)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="retrato: %(levelname)s %(message)s")
    log = logging.getLogger("retrato")

    cluster = Cluster(args.kubeconfig)
    if cluster.erro:
        log.warning(cluster.erro.mensagem)  # a pagina abre mesmo assim, com a faixa
    else:
        log.info("contexto %s (cluster %s, %s)", cluster.contexto, cluster.cluster, cluster.servidor)
    try:
        srv = servidor(cluster, args.porta, args.intervalo)
    except OSError as e:
        log.error("não foi possível escutar em 127.0.0.1:%s (%s)", args.porta, e.strerror)
        return 3
    log.info("abra http://127.0.0.1:%s  (Ctrl+C para sair)", args.porta)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        log.info("encerrado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
