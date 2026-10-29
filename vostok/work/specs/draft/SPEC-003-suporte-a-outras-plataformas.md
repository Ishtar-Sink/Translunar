---
id: SPEC-003
title: "Suporte a outras plataformas"
status: draft
author: "Victor Batalha"
created_at: 2026-10-29T12:14:21Z
updated_at: 2026-10-29T12:14:21Z
tags: [plataformas, linux, windows, whisper, gpu, cuda, cpu, instalacao]
---

# Suporte a outras plataformas

Permitir que o Translunar rode fora do Mac com Apple Silicon: em Linux e, se viável, em Windows, com a transcrição na GPU (NVIDIA, com CUDA) ou na CPU. Hoje o projeto depende do macOS em três pontos — o motor de transcrição (`mlx-whisper`), o serviço do painel (LaunchAgent) e a publicação do nome na rede local (`dns-sd`) —, e a documentação de instalação é só para o Mac.

## Contexto

### O que será construído

Uma melhoria de portabilidade sobre o MVP da SPEC-001. O fluxo, o painel, a CLI e a skill não mudam: muda o que roda por baixo em cada sistema e como instalar.

### Dor e problema

- O Whisper é um modelo leve e roda bem em GPUs NVIDIA e até em CPU, mas o Translunar só aceita o `mlx-whisper`, que usa o MLX da Apple. Quem não tem um Mac com Apple Silicon não consegue usar o projeto.
- O repositório vai ser aberto: a instalação precisa servir para outras pessoas, não só para o `server` do Victor.
- O serviço do painel (LaunchAgent) e o nome `translunar.local` (`dns-sd`) são do macOS. No Linux, o equivalente é `systemd` e Avahi.
- Os arquivos de `deploy/` têm valores fixos desta instalação (`/Users/server` no plist e o IP `192.168.2.17` no bloco do Caddy).
- A skill `translate-subtitles` assume o alias SSH `server` e os caminhos padrão (`~/apps/translunar`, `~/translunar-dados`), sem configuração.

### O que já é independente de sistema

O painel (FastAPI), a fila de jobs, a queima com o ffmpeg/libass, a CLI `legendar` e a skill (que só precisa de SSH). A transcrição já passa pela interface `Transcriber` (`core/transcription.py`), então um motor novo entra como mais uma implementação.

## Recursos

- Motor de transcrição `faster-whisper`, com GPU (CUDA) ou CPU, escolhido no `config.yaml` (por exemplo, `transcricao.motor: mlx | faster-whisper` e `transcricao.dispositivo: auto | cuda | cpu`), com o mesmo modelo (`large-v3-turbo` ou equivalente) e a mesma saída de palavras com tempo, para a segmentação continuar igual.
- Progresso da transcrição também no motor novo, até 100%, como no `mlx-whisper`.
- Extras de instalação por plataforma no `pyproject.toml` (por exemplo, `mac` e `cuda`/`cpu`), sem obrigar quem usa Mac a instalar o `faster-whisper` e vice-versa.
- Serviço do painel no Linux com uma unit do `systemd` (de usuário), equivalente ao LaunchAgent.
- Nome na rede local no Linux com Avahi, equivalente ao `dns-sd`.
- Arquivos de `deploy/` como modelos, sem valores fixos desta instalação (pasta pessoal, IP), gerados ou ajustados na instalação.
- Skill `translate-subtitles` com o host SSH e os caminhos configuráveis (com os valores atuais como padrão).
- README com a instalação por plataforma (macOS, Linux e, se couber, Windows) e a tabela de plataformas atualizada.

## Detalhes Técnicos

- Python 3.11+, `uv`, FastAPI; o `faster-whisper` usa CTranslate2 (CUDA 12 e cuDNN na GPU NVIDIA; `int8` na CPU).
- O `faster-whisper` devolve segmentos com `words` (início, fim e texto), compatível com a entrada da segmentação atual.
- No Linux, o `ffmpeg` dos pacotes da distribuição normalmente já tem libass; o `check_libass` atual continua valendo.
- Windows: avaliar no refinamento se entra no escopo (serviço, caminhos e acesso) ou fica para depois; uma opção é recomendar WSL2 com GPU.
- AMD (ROCm) e Intel: fora do escopo inicial, a menos que o refinamento mostre que é simples.

## Roteiro de Testes

- Transcrição com o `faster-whisper` em CPU no WSL/Linux de desenvolvimento, gerando um `pt.srt` válido para um vídeo curto.
- Transcrição com GPU NVIDIA, se houver uma máquina disponível.
- Testes da escolha do motor pelo `config.yaml` e da mensagem clara quando o motor escolhido não está instalado (código de saída 5).
- Instalação seguindo o README em Linux, do clone ao painel aberto em `https://translunar.local`.
- A suíte atual continua passando no Mac, com o `mlx-whisper`.

## Critérios de Aceite
- [ ] O Translunar transcreve em Linux com o `faster-whisper`, na GPU NVIDIA ou na CPU, com a mesma qualidade de segmentação do Mac.
- [ ] O motor e o dispositivo são escolhidos no `config.yaml`, e o Mac continua usando o `mlx-whisper` sem mudança.
- [ ] O painel sobe como serviço e volta sozinho depois de um reinício também no Linux.
- [ ] Os arquivos de `deploy/` e a skill não têm valores fixos de uma instalação específica.
- [ ] O README explica a instalação por plataforma.
