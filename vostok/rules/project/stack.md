# Stack

Define as tecnologias do projeto.

[project/stack-01]: Python 3.11+, com dependências gerenciadas pelo `uv` (`pyproject.toml` + `uv.lock`).
[project/stack-02]: Transcrição com `mlx-whisper` (modelo configurável). O `faster-whisper` fica como alternativa, atrás da mesma interface.
[project/stack-03]: Queima e inspeção com `ffmpeg` (libass, filtro `subtitles`) e `ffprobe`. A fonte vai embarcada no repositório e é carregada via `fontsdir`.
[project/stack-04]: Painel com FastAPI. O frontend é servido pelo próprio backend, sem etapa de build.
[project/stack-05]: Prévia no player HTML5, com a legenda em WebVTT gerada do `.srt` e a mesma fonte embarcada.
[project/stack-06]: Configuração em YAML.
[project/stack-07]: Nenhum SDK de IA nem chave de API no projeto (DEC-002).
