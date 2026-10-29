"""Orquestração com estado e lock: transcrever, registrar tradução e queimar.

A CLI e o painel só chamam estas funções ([project/architecture-01]).
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path

from translunar.core.burn import burn_cues
from translunar.core.config import Settings
from translunar.core.errors import UsageError
from translunar.core.lock import ClipLock
from translunar.core.models import VIDEO_EXTENSIONS, StepState
from translunar.core.probe import probe_video
from translunar.core.segmentation import Segment, Word
from translunar.core.srt import parse_srt, read_srt, write_srt_atomic
from translunar.core.state import (
    STATE_FILE,
    BurnRecord,
    ClipState,
    TranslationRecord,
    clip_dir,
    is_current,
    list_states,
    load_state,
    now_iso,
    refresh_outdated,
    save_state,
    sha256_file,
    validate_clip_id,
)
from translunar.core.transcription import (
    FakeTranscriber,
    MlxWhisperTranscriber,
    Transcriber,
    transcribe_to_cues,
)
from translunar.core.validation import Problem, validate_translation

TRANSCRIBER_ENV = "TRANSLUNAR_TRANSCRITOR"
_FAKE_TEXT = "Olá, este é um teste do Translunar."
_LANG_RE = re.compile(r"^[a-z]{2,3}$")
_PROGRESS_STEP = 0.1

ProgressCallback = Callable[[float], None]


def _noop(_progress: float) -> None:
    return None


def transcriber_for(settings: Settings) -> Transcriber:
    """Dublê com `TRANSLUNAR_TRANSCRITOR=falso`; senão o mlx-whisper."""
    if os.environ.get(TRANSCRIBER_ENV) == "falso":
        tokens = _FAKE_TEXT.split()
        start, end = 0.5, 3.0
        step = (end - start) / len(tokens)
        words = tuple(
            Word(start_s=start + i * step, end_s=start + (i + 1) * step, text=token)
            for i, token in enumerate(tokens)
        )
        return FakeTranscriber([Segment(start, end, _FAKE_TEXT, words)])
    return MlxWhisperTranscriber(settings.transcription.model)


def find_video(settings: Settings, clip_id: str) -> Path:
    """O arquivo de `entrada/` cujo nome sem extensão é o `clip_id`."""
    validate_clip_id(clip_id)
    if settings.input_dir.is_dir():
        for path in sorted(settings.input_dir.iterdir()):
            if path.is_file() and path.stem == clip_id and path.suffix.lower() in VIDEO_EXTENSIONS:
                return path
    raise UsageError(f"corte não encontrado: {clip_id}")


def _persisting_progress(
    directory: Path,
    state: ClipState,
    set_progress: Callable[[float], None],
    on_progress: ProgressCallback,
) -> ProgressCallback:
    """Callback que grava o `estado.json` no máximo a cada 10% de avanço (RF-31)."""
    last = 0.0

    def callback(value: float) -> None:
        nonlocal last
        set_progress(value)
        if value - last >= _PROGRESS_STEP:
            last = value
            save_state(directory, state)
        on_progress(value)

    return callback


def _hash_or_none(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() else None


def _translation_hashes(directory: Path, state: ClipState) -> dict[str, str | None]:
    return {lang: _hash_or_none(directory / f"{lang}.srt") for lang in state.translations}


def _refresh(directory: Path, state: ClipState) -> None:
    refresh_outdated(
        state, _hash_or_none(directory / "pt.srt"), _translation_hashes(directory, state)
    )


def _load_existing(directory: Path, clip_id: str) -> ClipState:
    if not (directory / STATE_FILE).is_file():
        raise UsageError(f"corte não encontrado: {clip_id}")
    return load_state(directory, clip_id, "")


def run_transcription(
    settings: Settings,
    clip_id: str,
    transcriber: Transcriber,
    force: bool = False,
    on_progress: ProgressCallback = _noop,
) -> ClipState:
    """Transcreve o corte e grava o `pt.srt`. Sem `force`, um `pt.srt` existente é preservado."""
    video = find_video(settings, clip_id)
    directory = clip_dir(settings.output_dir, clip_id)
    with ClipLock(directory):
        state = load_state(directory, clip_id, video.name)
        pt_path = directory / "pt.srt"
        if not force and pt_path.exists():
            return state  # RF-24 e RN-03: a edição manual nunca é sobrescrita sem force
        state.video = video.name
        record = state.transcription
        record.state = StepState.TRANSCREVENDO
        record.progress = 0.0
        record.error = None
        record.updated_at = now_iso()
        save_state(directory, state)

        def set_progress(value: float) -> None:
            record.progress = value

        callback = _persisting_progress(directory, state, set_progress, on_progress)
        try:
            probe, cues = transcribe_to_cues(
                video, transcriber, settings.limits, settings.burn.ffprobe, callback
            )
            write_srt_atomic(pt_path, cues)
            state.probe = probe
            record.input_hash = sha256_file(video)
            record.srt_hash = sha256_file(pt_path)
            record.state = StepState.TRANSCRITO
            record.progress = 1.0
            record.updated_at = now_iso()
            _refresh(directory, state)
            save_state(directory, state)
        except Exception as error:
            record.state = StepState.ERRO
            record.error = str(error)
            record.updated_at = now_iso()
            save_state(directory, state)
            raise
        on_progress(1.0)
        return state


def save_pt_srt(settings: Settings, clip_id: str, text: str) -> ClipState:
    """Grava o `pt.srt` editado. Texto inválido levanta `SrtParseError` sem gravar (CB-12)."""
    cues = parse_srt(text)
    directory = clip_dir(settings.output_dir, clip_id)
    with ClipLock(directory):
        state = _load_existing(directory, clip_id)
        pt_path = directory / "pt.srt"
        write_srt_atomic(pt_path, cues)
        state.transcription.srt_hash = sha256_file(pt_path)
        if state.transcription.state == StepState.AGUARDANDO:
            state.transcription.state = StepState.TRANSCRITO
        state.transcription.updated_at = now_iso()
        _refresh(directory, state)
        save_state(directory, state)
        return state


def register_translation(
    settings: Settings, srt_path: Path
) -> tuple[ClipState | None, list[Problem]]:
    """Valida `<idioma>.srt` contra o `pt.srt` e, se aprovado, registra no estado (RF-20)."""
    resolved = srt_path.resolve()
    language = resolved.stem
    directory = resolved.parent
    clip_id = directory.name
    if (
        resolved.suffix != ".srt"
        or directory.parent != settings.output_dir.resolve()
        or language == "pt"
        or not _LANG_RE.fullmatch(language)
    ):
        raise UsageError(
            f"caminho inválido: use {settings.output_dir}/<corte>/<idioma>.srt "
            "(idioma diferente de pt)"
        )
    validate_clip_id(clip_id)
    if not (settings.languages_dir / f"{language}.yaml").is_file():
        raise UsageError("idioma sem perfil: crie config/idiomas/<idioma>.yaml")
    pt_path = directory / "pt.srt"
    if not pt_path.is_file():
        raise UsageError(f"pt.srt ausente em {clip_id}: transcreva o corte antes")
    if not resolved.is_file():
        raise UsageError(f"arquivo não encontrado: {srt_path}")

    problems = validate_translation(
        read_srt(pt_path), resolved.read_text(encoding="utf-8"), settings.limits
    )
    if problems:
        return None, problems
    state = load_state(directory, clip_id, "")
    state.translations[language] = TranslationRecord(
        StepState.TRADUZIDO, sha256_file(resolved), sha256_file(pt_path), now_iso()
    )
    _refresh(directory, state)
    save_state(directory, state)
    return state, []


def refresh_clip(settings: Settings, clip_id: str) -> ClipState:
    """Recalcula os hashes atuais, marca o que ficou desatualizado e grava."""
    directory = clip_dir(settings.output_dir, clip_id)
    state = _load_existing(directory, clip_id)
    _refresh(directory, state)
    save_state(directory, state)
    return state


def list_clip_states(settings: Settings, clip_id: str | None = None) -> list[ClipState]:
    """Estados dos cortes com a desatualização calculada em memória, sem gravar."""
    states = list_states(settings.output_dir)
    if clip_id is not None:
        validate_clip_id(clip_id)
        states = [s for s in states if s.clip_id == clip_id]
        if not states:
            raise UsageError(f"corte não encontrado: {clip_id}")
    for state in states:
        _refresh(settings.output_dir / state.clip_id, state)
    return states


def run_burn(
    settings: Settings,
    clip_id: str,
    language: str,
    force: bool = False,
    on_progress: ProgressCallback = _noop,
) -> ClipState:
    """Queima o `<idioma>.srt` no vídeo. Tradução ausente ou desatualizada é recusada (CB-14)."""
    if not _LANG_RE.fullmatch(language) or language == "pt":
        raise UsageError(f"idioma inválido: {language}")
    directory = clip_dir(settings.output_dir, clip_id)
    if not (directory / STATE_FILE).is_file():
        raise UsageError(f"corte não encontrado: {clip_id}")
    with ClipLock(directory):
        state = refresh_clip(settings, clip_id)
        translation = state.translations.get(language)
        if translation is None or translation.state != StepState.TRADUZIDO:
            raise UsageError(
                f"tradução de {language} ausente ou desatualizada: traduza e valide de novo"
            )
        output = directory / f"{language}.mp4"
        burn = state.burns.get(language)
        if (
            burn is not None
            and output.exists()
            and is_current(
                burn.srt_hash, translation.srt_hash, burn.state, {StepState.PRONTO}, force
            )
        ):
            return state  # RF-24
        video = find_video(settings, clip_id)
        burn = state.burns[language] = BurnRecord(state=StepState.QUEIMANDO, updated_at=now_iso())
        save_state(directory, state)

        def set_progress(value: float) -> None:
            burn.progress = value

        callback = _persisting_progress(directory, state, set_progress, on_progress)
        try:
            probe = state.probe or probe_video(video, settings.burn.ffprobe)
            state.probe = probe
            burn_cues(
                video,
                read_srt(directory / f"{language}.srt"),
                output,
                probe,
                settings.style,
                settings.burn,
                settings.font_path,
                callback,
            )
            burn.state = StepState.PRONTO
            burn.progress = 1.0
            burn.srt_hash = translation.srt_hash
            burn.error = None
            burn.updated_at = now_iso()
            save_state(directory, state)
        except Exception as error:
            burn.state = StepState.ERRO
            burn.error = str(error)
            burn.updated_at = now_iso()
            save_state(directory, state)
            raise
        on_progress(1.0)
        return state
