# Testes

Define como o projeto é testado.

[project/testing-01]: Testes com `pytest`.
[project/testing-02]: Os testes não dependem do Claude Code: as traduções são simuladas com `.srt` fixos por idioma.
[project/testing-03]: A integração de mídia usa um vídeo sintético 9:16 gerado com ffmpeg e confere resolução, duração e áudio com o `ffprobe` depois da queima.
[project/testing-04]: Os testes da API do painel rodam com o worker simulado.
