"""Conversão de legendas para WebVTT, com a posição do estilo (RN-08)."""

from __future__ import annotations

from collections.abc import Sequence

from translunar.core.models import Cue, SubtitleStyle
from translunar.core.srt import format_timestamp


def _vtt_timestamp(ms: int) -> str:
    return format_timestamp(ms).replace(",", ".")


def srt_to_webvtt(cues: Sequence[Cue], style: SubtitleStyle | None = None) -> str:
    """Converte as legendas em WebVTT; com `style`, acrescenta line/position/size/align."""
    settings = ""
    if style is not None:
        settings = (
            f" line:{100 - style.margin_bottom_pct:g}%,end position:50%"
            f" size:{100 - 2 * style.margin_side_pct:g}% align:center"
        )
    blocks = [
        f"{_vtt_timestamp(c.start_ms)} --> {_vtt_timestamp(c.end_ms)}{settings}\n{c.text}"
        for c in cues
    ]
    return "WEBVTT\n\n" + "\n\n".join(blocks) + "\n"
