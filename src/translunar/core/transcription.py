"""Transcrição em pt-BR com o mlx-whisper e a rota do vídeo até as legendas (RF-06)."""

from __future__ import annotations

import importlib
import io
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol
from unittest import mock

from translunar.core.errors import DependencyMissingError, NoSpeechError
from translunar.core.models import Cue, ProbeResult, SubtitleLimits
from translunar.core.probe import probe_video, require_audio
from translunar.core.segmentation import Segment, Word, segment_words

logger = logging.getLogger(__name__)

# Progresso de 0.0 a 1.0.
ProgressCallback = Callable[[float], None]


class Transcriber(Protocol):
    """Qualquer transcritor: recebe o vídeo e devolve segmentos com palavras e tempos."""

    def transcribe(
        self, media: Path, duration_s: float, on_progress: ProgressCallback
    ) -> list[Segment]: ...


def _make_progress_bar(on_progress: ProgressCallback) -> type[Any] | None:
    """Cria a subclasse de tqdm que repassa o avanço; None se o tqdm não existir."""
    try:
        import tqdm
    except ImportError:
        return None

    class _ProgressBar(tqdm.tqdm):  # type: ignore[misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["disable"] = False
            kwargs["file"] = io.StringIO()
            super().__init__(*args, **kwargs)

        def update(self, n: float | None = 1) -> bool | None:
            result = super().update(n)
            if self.total:
                on_progress(min(self.n / self.total, 0.99))
            return result

    return _ProgressBar


class MlxWhisperTranscriber:
    """Adaptador do mlx-whisper (só roda no Mac com Apple Silicon, o server)."""

    def __init__(self, model: str) -> None:
        self.model = model

    def transcribe(
        self, media: Path, duration_s: float, on_progress: ProgressCallback
    ) -> list[Segment]:
        try:
            import mlx_whisper
        except ImportError as exc:
            raise DependencyMissingError(
                "mlx-whisper não instalado: rode uv sync --extra mac no server"
            ) from exc

        def run() -> dict[str, Any]:
            result: dict[str, Any] = mlx_whisper.transcribe(
                str(media),
                path_or_hf_repo=self.model,
                language="pt",
                word_timestamps=True,
                condition_on_previous_text=False,
                verbose=False,
            )
            return result

        result = self._run_with_progress(run, on_progress)
        on_progress(1.0)
        return _to_segments(result)

    @staticmethod
    def _run_with_progress(
        run: Callable[[], dict[str, Any]], on_progress: ProgressCallback
    ) -> dict[str, Any]:
        """Roda a transcrição trocando o tqdm interno do mlx-whisper (inferência H)."""
        try:
            # `mlx_whisper.transcribe` no pacote é a função; o módulo vem do importlib.
            module = importlib.import_module("mlx_whisper.transcribe")
            tqdm_module = module.tqdm
            bar = _make_progress_bar(on_progress)
            if bar is None:
                raise AttributeError("tqdm indisponível")
            patcher = mock.patch.object(tqdm_module, "tqdm", bar)
        except (ImportError, AttributeError) as exc:
            logger.warning("sem progresso intermediário da transcrição: %s", exc)
            return run()
        with patcher:
            return run()


def _to_segments(result: dict[str, Any]) -> list[Segment]:
    """Converte o resultado do mlx-whisper em `Segment` e `Word`."""
    segments: list[Segment] = []
    for raw in result.get("segments") or []:
        words = tuple(
            Word(start_s=float(w["start"]), end_s=float(w["end"]), text=str(w["word"]))
            for w in raw.get("words") or []
        )
        segments.append(
            Segment(
                start_s=float(raw["start"]),
                end_s=float(raw["end"]),
                text=str(raw.get("text", "")),
                words=words,
            )
        )
    return segments


class FakeTranscriber:
    """Dublê para testes e para a CLI em modo de teste: devolve segmentos prontos."""

    def __init__(self, segments: list[Segment]) -> None:
        self.segments = segments

    def transcribe(
        self, media: Path, duration_s: float, on_progress: ProgressCallback
    ) -> list[Segment]:
        on_progress(0.5)
        on_progress(1.0)
        return self.segments


def transcribe_to_cues(
    video: Path,
    transcriber: Transcriber,
    limits: SubtitleLimits,
    ffprobe: str,
    on_progress: ProgressCallback,
) -> tuple[ProbeResult, list[Cue]]:
    """Do vídeo às legendas. Não grava arquivo: quem grava o pt.srt é a pipeline (RN-03)."""
    probe = probe_video(video, ffprobe)
    require_audio(probe)
    segments = transcriber.transcribe(video, probe.duration_s, on_progress)
    spoken = [s for s in segments if s.text.strip() or any(w.text.strip() for w in s.words)]
    if not any(w.text.strip() for s in spoken for w in (s.words or (Word(0, 0, s.text),))):
        raise NoSpeechError("nenhuma fala detectada")
    return probe, segment_words(spoken, limits)
