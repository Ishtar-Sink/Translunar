"""Exceções do Translunar. Cada uma carrega o código de saída da CLI (contrato da SPEC-001)."""

from __future__ import annotations


class TranslunarError(Exception):
    """Erro de execução genérico (código 1)."""

    exit_code = 1


class ConfigError(TranslunarError):
    """Configuração ausente ou inválida."""


class ProbeError(TranslunarError):
    """O ffprobe não conseguiu ler o vídeo, ou o vídeo não serve (ex.: sem áudio)."""


class NoSpeechError(TranslunarError):
    """A transcrição não encontrou fala."""


class SrtParseError(TranslunarError):
    """SRT com formato inválido. `line` é a linha (1-based) onde o erro foi encontrado."""

    def __init__(self, line: int, message: str) -> None:
        super().__init__(f"linha {line}: {message}")
        self.line = line


class UsageError(TranslunarError):
    """Uso inválido: argumento ou corte inexistente (código 2)."""

    exit_code = 2


class ValidationFailedError(TranslunarError):
    """Validação de legenda recusada (código 3)."""

    exit_code = 3


class ClipLockedError(TranslunarError):
    """Corte bloqueado por outro processo ou em processamento (código 4)."""

    exit_code = 4


class DependencyMissingError(TranslunarError):
    """Dependência ausente: ffmpeg sem libass, mlx-whisper, fonte (código 5)."""

    exit_code = 5
