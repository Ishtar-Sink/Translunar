"""Estado persistente de cada corte (`estado.json`), hashes, ids e desatualização."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from translunar.core.errors import UsageError
from translunar.core.models import ProbeResult, StepState

STATE_FILE = "estado.json"
_CLIP_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_CHUNK = 1024 * 1024


@dataclass
class TranscriptionRecord:
    """Estado da transcrição do corte."""

    state: StepState = StepState.AGUARDANDO
    progress: float = 0.0
    input_hash: str | None = None
    srt_hash: str | None = None
    error: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": str(self.state),
            "progress": self.progress,
            "input_hash": self.input_hash,
            "srt_hash": self.srt_hash,
            "error": self.error,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TranscriptionRecord:
        return cls(
            state=StepState(data.get("state", StepState.AGUARDANDO)),
            progress=float(data.get("progress", 0.0)),
            input_hash=data.get("input_hash"),
            srt_hash=data.get("srt_hash"),
            error=data.get("error"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class TranslationRecord:
    """Estado da tradução de um idioma."""

    state: StepState = StepState.TRADUZIDO
    srt_hash: str = ""
    source_hash: str = ""
    validated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": str(self.state),
            "srt_hash": self.srt_hash,
            "source_hash": self.source_hash,
            "validated_at": self.validated_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TranslationRecord:
        return cls(
            state=StepState(data.get("state", StepState.TRADUZIDO)),
            srt_hash=data.get("srt_hash", ""),
            source_hash=data.get("source_hash", ""),
            validated_at=data.get("validated_at", ""),
        )


@dataclass
class BurnRecord:
    """Estado da queima de um idioma."""

    state: StepState = StepState.AGUARDANDO
    progress: float = 0.0
    srt_hash: str | None = None
    error: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": str(self.state),
            "progress": self.progress,
            "srt_hash": self.srt_hash,
            "error": self.error,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BurnRecord:
        return cls(
            state=StepState(data.get("state", StepState.AGUARDANDO)),
            progress=float(data.get("progress", 0.0)),
            srt_hash=data.get("srt_hash"),
            error=data.get("error"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class ClipState:
    """Conteúdo do `estado.json` de um corte."""

    clip_id: str
    video: str
    probe: ProbeResult | None = None
    transcription: TranscriptionRecord = field(default_factory=TranscriptionRecord)
    translations: dict[str, TranslationRecord] = field(default_factory=dict)
    burns: dict[str, BurnRecord] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        probe: dict[str, Any] | None = None
        if self.probe is not None:
            probe = {
                "width": self.probe.width,
                "height": self.probe.height,
                "duration_s": self.probe.duration_s,
                "has_audio": self.probe.has_audio,
            }
        return {
            "clip_id": self.clip_id,
            "video": self.video,
            "probe": probe,
            "transcription": self.transcription.to_dict(),
            "translations": {k: v.to_dict() for k, v in self.translations.items()},
            "burns": {k: v.to_dict() for k, v in self.burns.items()},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ClipState:
        raw_probe = data.get("probe")
        probe = (
            ProbeResult(
                width=int(raw_probe["width"]),
                height=int(raw_probe["height"]),
                duration_s=float(raw_probe["duration_s"]),
                has_audio=bool(raw_probe["has_audio"]),
            )
            if raw_probe
            else None
        )
        return cls(
            clip_id=data["clip_id"],
            video=data["video"],
            probe=probe,
            transcription=TranscriptionRecord.from_dict(data.get("transcription") or {}),
            translations={
                k: TranslationRecord.from_dict(v)
                for k, v in (data.get("translations") or {}).items()
            },
            burns={k: BurnRecord.from_dict(v) for k, v in (data.get("burns") or {}).items()},
        )


def now_iso() -> str:
    """Data e hora atuais em UTC, com `Z` e sem microssegundos."""
    return datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    """Hash do arquivo, lido em blocos de 1 MiB, no formato `sha256:<hex>`."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def validate_clip_id(clip_id: str) -> str:
    """Aceita só ids seguros para nome de pasta (RN-11, CB-07)."""
    if not _CLIP_ID_RE.fullmatch(clip_id) or ".." in clip_id:
        raise UsageError(f"id de corte inválido: {clip_id!r}")
    return clip_id


def clip_id_for_video(video_name: str) -> str:
    """Id do corte: o nome do vídeo sem a extensão, validado."""
    return validate_clip_id(Path(video_name).stem)


def clip_dir(output_dir: Path, clip_id: str) -> Path:
    """Pasta do corte dentro de `output_dir`, garantindo que não escapa dela."""
    validate_clip_id(clip_id)
    target = output_dir / clip_id
    if not target.resolve().is_relative_to(output_dir.resolve()):
        raise UsageError(f"id de corte inválido: {clip_id!r}")
    return target


def load_state(directory: Path, clip_id: str, video: str) -> ClipState:
    """Lê o `estado.json` da pasta ou devolve um estado novo."""
    path = directory / STATE_FILE
    if not path.exists():
        return ClipState(clip_id, video)
    return ClipState.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_state(directory: Path, state: ClipState) -> None:
    """Grava o estado de forma atômica (arquivo temporário + `os.replace`)."""
    directory.mkdir(parents=True, exist_ok=True)
    tmp = directory / f".{STATE_FILE}.tmp"
    tmp.write_text(
        json.dumps(state.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    os.replace(tmp, directory / STATE_FILE)


def is_current(
    recorded_hash: str | None,
    current_hash: str | None,
    state: StepState,
    done_states: Collection[StepState],
    force: bool,
) -> bool:
    """`True` quando a etapa já está pronta com a mesma entrada e não precisa ser refeita."""
    return (
        not force
        and state in done_states
        and recorded_hash is not None
        and current_hash is not None
        and recorded_hash == current_hash
    )


def refresh_outdated(
    state: ClipState,
    pt_hash: str | None,
    translation_hashes: Mapping[str, str | None],
) -> list[str]:
    """Marca como desatualizado o que depende de entrada alterada (RF-23). Devolve o que mudou."""
    changed: list[str] = []
    skip = {StepState.TRANSCREVENDO, StepState.QUEIMANDO, StepState.ERRO}
    for lang, tr in state.translations.items():
        if tr.state in skip or tr.state == StepState.DESATUALIZADO:
            continue
        current = translation_hashes.get(lang)
        if pt_hash != tr.source_hash or (current is not None and current != tr.srt_hash):
            tr.state = StepState.DESATUALIZADO
            changed.append(f"translations.{lang}")
    for lang, burn in state.burns.items():
        if burn.state != StepState.PRONTO:
            continue
        source = state.translations.get(lang)
        if (
            source is None
            or source.state == StepState.DESATUALIZADO
            or burn.srt_hash != source.srt_hash
        ):
            burn.state = StepState.DESATUALIZADO
            changed.append(f"burns.{lang}")
    return changed


def mark_interrupted(state: ClipState) -> bool:
    """Etapas em andamento viram `INTERROMPIDO` (RN-10). Devolve `True` se mudou algo."""
    changed = False
    if state.transcription.state == StepState.TRANSCREVENDO:
        state.transcription.state = StepState.INTERROMPIDO
        changed = True
    for burn in state.burns.values():
        if burn.state == StepState.QUEIMANDO:
            burn.state = StepState.INTERROMPIDO
            changed = True
    return changed


def list_states(output_dir: Path) -> list[ClipState]:
    """Estados de todos os cortes de `output_dir`, ordenados por `clip_id`."""
    if not output_dir.is_dir():
        return []
    states = [
        ClipState.from_dict(json.loads((sub / STATE_FILE).read_text(encoding="utf-8")))
        for sub in output_dir.iterdir()
        if sub.is_dir() and (sub / STATE_FILE).is_file()
    ]
    return sorted(states, key=lambda s: s.clip_id)
