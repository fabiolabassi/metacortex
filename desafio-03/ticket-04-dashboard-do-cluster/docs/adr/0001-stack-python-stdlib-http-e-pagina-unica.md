# ADR-0001: Python + servidor HTTP da biblioteca padrão + página única sem build

- Status: aceito
- Data: 2026-10-27

## Contexto

Quem mantém é um time de infraestrutura. Eles escrevem Python e Bash, leem
YAML o dia todo e não mantêm frontend. A aplicação roda na estação de quem
opera, aberta e fechada várias vezes por dia. O Ticket 03 já é Python.

## Decisão

- Backend em **Python 3.10+**, servidor `http.server.ThreadingHTTPServer` da
  biblioteca padrão, servindo uma API JSON só de GET.
- Frontend: **um arquivo HTML** com CSS e JavaScript sem framework e sem
  etapa de build, servido pelo próprio processo.
- Única dependência: o cliente oficial do Kubernetes (ADR-0002).

## Alternativas consideradas

| Alternativa | O que se ganha | O que se perde |
|---|---|---|
| **Python + stdlib + página única** (escolhida) | uma dependência; `python3 -m retrato` e pronto; o time lê o código inteiro (~600 linhas); mesma linguagem do Ticket 03 | sem componentes prontos de UI; o JS da tabela é escrito à mão; o `http.server` não serve para multiusuário (e não precisa) |
| **Go + client-go + templates (ou HTMX)** | binário único, sem runtime; client-go é a referência de comportamento (informers, auth plugins); tipagem forte | o time não mantém Go hoje; toolchain e cross-compile no pipeline; curva de client-go (informers, listers) maior que o problema da primeira fatia |
| **TypeScript: Node + @kubernetes/client-node + React/Vite** | ecossistema de UI rico (tabelas, filtros); tipagem dos objetos da API | dois mundos para manter (Node + build de frontend); `node_modules` com centenas de pacotes na estação de quem tem acesso a produção; o time não escreve TS |
| **Python + FastAPI/Flask + Jinja** | roteamento e validação prontos; templates no servidor | mais 5 a 15 dependências transitivas para quatro rotas GET; o ganho aparece só quando houver escrita ou autenticação, e as duas estão fora do escopo |
| **TUI (Textual, k9s-like)** | mais perto do terminal | quatro tabelas largas não cabem bem em 80 colunas; o k9s já existe e o time não o adotou para triagem |

## Consequências

- (+) Instalação: `pip install kubernetes` + rodar o módulo.
- (+) Superfície pequena para auditar numa estação com credencial de produção.
- (−) Sem reatividade fina no frontend: a tabela é redesenhada a cada atualização. Aceitável para um namespace.
- (−) Se a aplicação crescer (logs em streaming, várias abas), FastAPI volta à mesa.
