---
type: decision
title: "Decisões"
description: "Decisões estruturantes do projeto e o motivo de cada uma. Consulte antes de decidir algo que afete arquitetura, stack, dados, contratos ou convenções, e quando houver ambiguidade."
updated_at: 2026-10-29T01:03:45Z
---

# Decisões

Decisões estruturantes do projeto e o motivo de cada uma. Consulte antes de decidir algo que afete arquitetura, stack, dados, contratos ou convenções, e quando houver ambiguidade.

Entradas criadas por `vostok memory add` e consultadas por `vostok memory search`. Não carregue este arquivo inteiro.

## DEC-001: Localização feita pelo Claude Code no chat, fora da pipeline

- **Data:** 2026-10-28
- **Status:** substituída
- **Tags:** arquitetura, pipeline, localizacao, claude-code, painel
- **Origem:** Conversa com o usuário durante o init do harness, antes do refinamento da SPEC-001.
- **Contexto:** A SPEC-001 previa a localização dentro da pipeline, via SDK `anthropic` com `ANTHROPIC_API_KEY`. O usuário quer conduzir a pipeline pelo chat do Claude Code e revisar a transcrição antes de localizar.
- **Decisão:** A pipeline não chama nenhum modelo de IA. Ela roda em duas fases separadas por uma aprovação no painel. Fase 1: probe → transcrição → segmentação → prévia rápida com legenda pt-br queimada. O usuário revisa e aprova no painel. O Claude Code, pelo chat, conecta ao Mac por SSH, lê o `pt.srt` aprovado, localiza e devolve um `.srt` por idioma. Fase 2: validação das legendas → render em segundo plano, com progresso persistido e exibido no painel.
- **Alternativas descartadas:** Localização pela API da Anthropic dentro da pipeline, com chave em variável de ambiente (desenho original da SPEC-001).
- **Consequências:** Sem chave nem custo de tokens na pipeline (sai do resumo o custo estimado). A localização depende de uma sessão de chat. A CLI precisa ser não interativa, com saída legível por máquina. O progresso de cada etapa precisa ser persistido em disco. A SPEC-001 foi revista em recursos, localização, segurança e testes.
- **Substitui:** Nenhuma

## DEC-002: Painel conduz a pipeline e o Claude Code só traduz, por skill

- **Data:** 2026-10-29
- **Status:** ativa
- **Tags:** arquitetura, pipeline, localizacao, claude-code, painel, skill, previa
- **Origem:** Conversa com o usuário durante o init do harness, antes do refinamento da SPEC-001.
- **Contexto:** Na DEC-001, o Claude Code disparava as fases por SSH e havia uma aprovação formal. O usuário prefere que o painel conduza tudo o que não depende de IA, deixando ao Claude Code só a tradução, e quer prévia da legenda no vídeo já na transcrição e também na tradução, antes da queima.
- **Decisão:** A pipeline não chama IA. No painel, o usuário escolhe um vídeo do acervo de `entrada/` e dispara a transcrição, com progresso. Ao fim da transcrição, o painel já exibe o vídeo com a legenda pt-BR sobreposta, permite editar o `pt.srt` e mostra o caminho dele no Mac. O usuário cita esse caminho no Claude Code, e uma skill do projeto (ex.: `translate-subtitles`) pergunta os idiomas de saída, lê o `pt.srt` por SSH, localiza mantendo ids e timestamps (sincronizado com o vídeo), grava `<idioma>.srt` ao lado e roda a validação da CLI. O painel detecta as traduções, mostra a prévia de cada idioma sobre o vídeo e dispara a queima. As prévias usam o player do navegador com a legenda sobreposta (WebVTT gerado do `.srt`, com a fonte e o estilo da legenda final), sem render.
- **Alternativas descartadas:** DEC-001 (Claude Code disparando as fases por SSH, com aprovação formal). Prévia renderizada com ffmpeg (fiel ao libass, mas lenta e refeita a cada edição). API da Anthropic dentro da pipeline.
- **Consequências:** O agente não opera fila nem estado: só lê e escreve arquivos e roda a validação. Não há aprovação formal. Os idiomas são escolhidos a cada tradução; `en`, `es` e `fr` seguem como perfis do MVP. A prévia no navegador pode diferir levemente da legenda queimada pelo libass. A skill de tradução é um entregável da SPEC-001.
- **Substitui:** DEC-001
