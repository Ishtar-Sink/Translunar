# Translunar

Pipeline de legendas multilíngues para vídeo vertical. Você deixa cortes em português numa pasta e o Translunar devolve, para cada um, versões em inglês, espanhol e francês com a legenda queimada no vídeo, prontas para postar em Reels, TikTok, Shorts e X. O texto não é traduzido ao pé da letra: é localizado, para que quem assiste entenda nos próprios termos.

Faz parte do ecossistema [Ishtar Sink](https://github.com/Ishtar-Sink): código aberto (AGPL-3.0), pensado para autohospedagem, sem conta, sem plano pago e sem telemetria. O vídeo não sai da sua máquina; só o texto transcrito vai para a API de IA.

> **Em desenvolvimento.** Este repositório ainda não tem código. O que está descrito abaixo é o escopo do MVP, definido na [SPEC-001](vostok/work/specs/draft/SPEC-001-mvp-pipeline-de-legendas-multilingues.md).

## O que ele faz

- **Transcrição local** do português com Whisper rodando no Apple Silicon, gerando um `pt.srt` com timestamps.
- **Revisão opcional** antes de localizar: com `--revisar`, a execução para depois da transcrição, você corrige o `pt.srt` e roda de novo. Um erro de transcrição corrigido ali não se espalha para os outros idiomas.
- **Localização, não tradução literal.** Expressões, humor e referências brasileiras viram o equivalente que faz sentido em cada idioma, usando um perfil por idioma, um glossário de termos fixos e, se você quiser, um arquivo de contexto por vídeo explicando o que só um brasileiro entenderia.
- **Variantes escolhidas para o maior público:** inglês internacional, espanhol neutro (latino-americano, sem *vosotros*) e francês da França.
- **Legenda pensada para 9:16:** no máximo 2 linhas, cerca de 30 caracteres por linha, velocidade de leitura controlada (até ~17 caracteres por segundo) e posição fora das áreas cobertas pela interface das plataformas.
- **Retomável por construção.** Rodar de novo não refaz o que já está pronto; mudou o `pt.srt`, o glossário, um perfil ou o contexto, refaz só os idiomas afetados. Falha num vídeo ou idioma não derruba o lote.
- **Idioma novo sem código:** qualquer idioma de alfabeto latino entra com um arquivo de perfil em `config/idiomas/`.
- **Painel web** para subir os cortes, acompanhar o processamento em tempo real, revisar o `pt.srt`, baixar os vídeos prontos (um a um ou em `.zip`) e apagar os antigos para liberar espaço. Uso pessoal, protegido por senha e restrito à rede local ou a uma VPN.

## Como funciona

```text
  entrada/corte-01.mp4
        │
        ├─ ffprobe ──────────── valida resolução, duração e áudio
        ├─ Whisper (local) ──── pt.srt
        ├─ pausa opcional ───── você revisa o pt.srt
        ├─ segmentação ──────── legendas curtas para vídeo vertical
        ├─ IA (só texto) ────── en.srt  es.srt  fr.srt   (localizados, com controle de leitura)
        └─ ffmpeg ───────────── en.mp4  es.mp4  fr.mp4   (legenda queimada, áudio intacto)
        │
  saida/corte-01/
```

A linha de comando e o painel usam o mesmo núcleo, sobre as mesmas pastas, com um lock por corte para que os dois nunca processem o mesmo vídeo ao mesmo tempo.

## Uso previsto

```bash
legendar run                 # processa tudo o que está em entrada/
legendar run --revisar       # para depois da transcrição para você revisar o pt.srt
legendar run --forcar        # refaz tudo, ignorando o que já está pronto
legendar painel              # sobe o painel web
```

Também haverá opções para escolher a pasta de entrada, os idiomas, pular o render e definir o paralelismo.

## Requisitos previstos

- Mac com Apple Silicon (desenvolvido num M1 Pro com 16 GB). A transcrição usa `mlx-whisper`; `faster-whisper` fica como alternativa para outras máquinas.
- Python 3.11+ com [`uv`](https://docs.astral.sh/uv/).
- `ffmpeg` com libass e `ffprobe`.
- Uma chave da API da Anthropic em `ANTHROPIC_API_KEY`, por variável de ambiente ou arquivo `.env` fora do git.

O Translunar foi pensado para ser operado por SSH. Rode os jobs longos dentro do `tmux`, e o painel dentro do `tmux` ou pelo `launchd`, para que nada morra se a conexão cair.

## Fora do MVP

Em ordem provável: títulos, descrições e hashtags localizados por plataforma; dublagem; publicação automática; pasta monitorada que processa cortes novos sozinha; idiomas com alfabeto não latino.

## Segurança em uma linha

O painel é de um usuário só e protegido por senha, mas não foi feito para a internet: acesse pela rede local ou por uma VPN privada, **nunca o exponha publicamente**.

## Sobre o nome

A injeção translunar é a queima de motor que tira a nave da órbita da Terra e a manda para outro mundo. O Translunar faz isso com o vídeo: tira o corte do público de origem e o lança para outros idiomas, com a legenda queimada na imagem.

## Licença

[AGPL-3.0](LICENSE).
