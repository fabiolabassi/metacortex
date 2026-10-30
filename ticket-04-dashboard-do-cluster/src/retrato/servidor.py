"""Servidor HTTP local. So GET (TRD §5, item 2): qualquer outro metodo e 405."""
import importlib.resources
import json
import logging
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from retrato import retrato
from retrato.leitura import FalhaDeLeitura

log = logging.getLogger("retrato")
NOME_NS = re.compile(r"^[a-z0-9]([-a-z0-9]{0,61}[a-z0-9])?$")


class Handler(BaseHTTPRequestHandler):
    cluster = None
    intervalo = 10
    server_version = "retrato"

    def _json(self, status, corpo):
        dados = json.dumps(corpo, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_GET(self):  # noqa: N802
        try:
            self._get()
        except Exception as e:  # noqa: BLE001 — nunca traceback para o navegador
            log.error("erro interno em %s: %s", self.path, type(e).__name__)
            self._json(500, {"erro": {"tipo": "interno", "mensagem": "Erro interno."}})

    def _get(self):
        caminho = self.path.split("?", 1)[0]
        if caminho == "/":
            html = importlib.resources.files("retrato").joinpath("static/index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                                        "script-src 'self' 'unsafe-inline'")
            self.end_headers()
            self.wfile.write(html)
        elif caminho == "/api/contexto":
            self._json(200, dict(self.cluster.info(), intervalo_s=self.intervalo))
        elif caminho == "/api/namespaces":
            try:
                self._json(200, {"itens": sorted(n.metadata.name for n in self.cluster.lista_namespaces())})
            except FalhaDeLeitura as e:
                self._json(200, {"erro": e.como_dict()})
        elif caminho.startswith("/api/retrato/"):
            ns = caminho.rsplit("/", 1)[1]
            if not NOME_NS.match(ns):
                self._json(400, {"erro": {"tipo": "uso", "mensagem": "Nome de namespace inválido."}})
                return
            self._json(200, retrato.monta(self.cluster, ns))
        else:
            self._json(404, {"erro": {"tipo": "uso", "mensagem": "Rota inexistente."}})

    def _so_leitura(self):
        self._json(405, {"erro": {"tipo": "somente_leitura",
                                  "mensagem": "O retrato é só leitura: apenas GET é aceito."}})

    do_POST = do_PUT = do_PATCH = do_DELETE = _so_leitura  # noqa: N815

    def log_message(self, fmt, *args):  # uma linha por requisicao, sem corpo
        log.debug("%s %s", self.command, self.path)


def servidor(cluster, porta, intervalo):
    Handler.cluster, Handler.intervalo = cluster, intervalo
    return ThreadingHTTPServer(("127.0.0.1", porta), Handler)
