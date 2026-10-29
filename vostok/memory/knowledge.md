---
type: knowledge
title: "Conhecimentos"
description: "Descobertas e peculiaridades do projeto sem documentação primária. Consulte antes de pesquisar ou investigar um assunto pouco documentado."
updated_at: 2026-10-29T02:15:56Z
---

# Conhecimentos

Descobertas e peculiaridades do projeto sem documentação primária. Consulte antes de pesquisar ou investigar um assunto pouco documentado.

Entradas criadas por `vostok memory add` e consultadas por `vostok memory search`. Não carregue este arquivo inteiro.

## KNW-001: ffmpeg do Homebrew no server não tem libass

- **Data:** 2026-10-29
- **Status:** válido
- **Tags:** ffmpeg, libass, legenda, queima, server, homebrew
- **Conhecimento:** O `ffmpeg` da fórmula padrão do Homebrew no `server` (9.0.1, `/opt/homebrew/bin/ffmpeg`) é compilado sem `--enable-libass` e não tem os filtros `subtitles` e `ass`, então não queima legendas. A fórmula `ffmpeg-full` (keg-only, em `/opt/homebrew/opt/ffmpeg-full/bin/`) tem o libass e é a que o Translunar usa, com o caminho em `queima.ffmpeg` e `queima.ffprobe` do `config.yaml`. O `ffmpeg` do WSL (`~/.local/bin/ffmpeg`) já tem o libass.
- **Como foi descoberto:** `ssh -T server 'ffmpeg -hide_banner -filters | grep subtitles'` não retornou nada, e `brew info ffmpeg-full` mostrou a fórmula disponível, durante o refinamento da SPEC-001.
- **Validade:** Enquanto o Homebrew mantiver a fórmula `ffmpeg` sem libass. Confira com `ffmpeg -filters` depois de atualizar.

## KNW-002: ruff 0.17 formata blocos Python dentro de Markdown

- **Data:** 2026-10-29
- **Status:** válido
- **Tags:** ruff, format, markdown, harness, tarefas, vostok
- **Conhecimento:** O `ruff format` 0.17 também formata os blocos de código Python dentro de arquivos `.md`. Sem exclusão no `pyproject.toml`, `uv run ruff format` na raiz percorre `vostok/` e `.claude/` (125 arquivos neste projeto) e reformata os blocos Python das tarefas aprovadas, o que muda o conteúdo depois da aprovação. O `ruff format --check` também passa a falhar por causa desses arquivos.
- **Como foi descoberto:** Na execução da TASK-01, o `uv run ruff format` reformatou `TASK-01.md` e `TASK-05.md` junto com o `tests/conftest.py`; `uv run ruff format --check -v` listou os `.md` de `vostok/` e `.claude/`. Os blocos foram restaurados a partir do conteúdo aprovado.
- **Validade:** Enquanto o ruff formatar Markdown por padrão. A proteção é excluir `*.md`, `vostok/` e `.claude/` em `[tool.ruff]`.

## KNW-003: Publicação de nomes .local e acesso ao GitHub no server

- **Data:** 2026-10-29
- **Status:** válido
- **Tags:** server, mdns, dns-sd, caddy, launchagent, github, deploy
- **Conhecimento:** No `server`, cada nome `.local` é publicado por um LaunchAgent próprio que roda `/usr/bin/dns-sd -P <Nome> _https._tcp local 443 <nome>.local 192.168.2.17` (`local.flare-mdns`, `local.translunar-mdns`). O `/opt/homebrew/etc/Caddyfile` traz o bloco do Nebula e importa o bloco de cada projeto com `import /Users/server/apps/<app>/deploy/...`; o Caddy roda pelo `brew services` e recarrega sem sudo com `caddy reload --config /opt/homebrew/etc/Caddyfile --adapter caddyfile`. O `server` não tem chave do GitHub nem `gh`: só clona repositórios públicos por HTTPS (Nebula). O Translunar é privado, então chega ao `server` por `rsync`, como o Flare.
- **Como foi descoberto:** Na TASK-09 da SPEC-001: o `git clone git@github.com:Ishtar-Sink/Translunar.git` falhou por autenticação; `pgrep -fl dns-sd`, `ls ~/Library/LaunchAgents` e o Caddyfile mostraram o mecanismo do Flare.
- **Validade:** Enquanto o `server` não tiver acesso ao GitHub e os nomes `.local` forem publicados por `dns-sd`. Confira com `ls ~/Library/LaunchAgents` e `pgrep -fl dns-sd`.
