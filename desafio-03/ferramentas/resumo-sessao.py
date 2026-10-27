#!/usr/bin/env python3
"""Resume uma sessao gravada com `claude -p --output-format stream-json --verbose`.

Mostra skills disparadas, ferramentas chamadas (na ordem), tokens, custo e
tempo. Usado como evidencia de execucao das skills e na comparacao com e sem
skill. Uso: python3 resumo-sessao.py SESSAO.jsonl [--md]
"""
import json
import sys


def resume(caminho):
    r = {"skills": [], "ferramentas": [], "mcp": [], "resultado": None}
    for linha in open(caminho, encoding="utf-8"):
        try:
            d = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if d.get("type") == "system" and d.get("subtype") == "init":
            r["modelo"] = d.get("model")
            r["mcp_servers"] = d.get("mcp_servers")
        if d.get("type") == "assistant":
            for c in d["message"].get("content", []):
                if c.get("type") != "tool_use":
                    continue
                nome, entrada = c["name"], c.get("input", {})
                if nome == "Skill":
                    r["skills"].append(entrada.get("skill"))
                if nome.startswith("mcp__"):
                    r["mcp"].append(nome)
                resumo = entrada.get("command") or entrada.get("file_path") or \
                    entrada.get("skill") or json.dumps(entrada, ensure_ascii=False)
                r["ferramentas"].append((nome, " ".join(str(resumo).split())[:140]))
        if d.get("type") == "result":
            r["resultado"] = d
    return r


def main():
    caminho = sys.argv[1]
    r = resume(caminho)
    res = r["resultado"] or {}
    u = res.get("usage") or {}
    entrada = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + \
        u.get("cache_read_input_tokens", 0)
    print("sessao:      {}".format(caminho))
    print("modelo:      {}".format(r.get("modelo")))
    print("skills:      {}".format(", ".join(r["skills"]) or "nenhuma"))
    print("tempo:       {:.1f}s".format(res.get("duration_ms", 0) / 1000))
    print("turnos:      {}".format(res.get("num_turns")))
    print("tokens:      entrada {} (cache lido {}), saida {}".format(
        entrada, u.get("cache_read_input_tokens", 0), u.get("output_tokens", 0)))
    print("custo:       US$ {:.4f}".format(res.get("total_cost_usd") or 0))
    print("ferramentas: {} chamadas ({} MCP)".format(len(r["ferramentas"]), len(r["mcp"])))
    for nome, resumo in r["ferramentas"]:
        print("  - {:<34} {}".format(nome, resumo))


if __name__ == "__main__":
    main()
