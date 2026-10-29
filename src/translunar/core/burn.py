"""Queima de legendas no vídeo com ffmpeg/libass: ASS, comando e progresso."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
from collections.abc import Callable, Sequence
from pathlib import Path

from translunar.core.config import BurnSettings
from translunar.core.errors import DependencyMissingError, TranslunarError
from translunar.core.models import Cue, ProbeResult, SubtitleStyle

_AUDIO_CODEC_ERRORS = ("codec not currently supported in container", "Could not find tag for codec")
_ASS_FILTER_LINE = re.compile(r"^\s*\S+\s+ass\s")


def hex_to_ass(color: str) -> str:
    """Converte `#RRGGBB` em `&H00BBGGRR` (formato de cor do ASS)."""
    value = color.lstrip("#")
    if len(value) != 6:
        raise TranslunarError(f"cor inválida (use #RRGGBB): {color}")
    red, green, blue = value[0:2], value[2:4], value[4:6]
    return f"&H00{blue}{green}{red}".upper()


def ass_timestamp(ms: int) -> str:
    """Formata milissegundos como `H:MM:SS.cc` (centésimos)."""
    centis = ms // 10
    hours, rest = divmod(centis, 360000)
    minutes, rest = divmod(rest, 6000)
    seconds, cs = divmod(rest, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{cs:02d}"


def cues_to_ass(
    cues: Sequence[Cue],
    width: int,
    height: int,
    style: SubtitleStyle,
    font_name: str = "Inter",
) -> str:
    """Gera o ASS com PlayRes igual ao vídeo, para o estilo em % virar pixels exatos (RN-08)."""
    font_size = round(width * style.size_pct_width / 100)
    outline = max(2, round(font_size * 0.08))
    margin_side = round(width * style.margin_side_pct / 100)
    margin_bottom = round(height * style.margin_bottom_pct / 100)
    primary = hex_to_ass(style.text_color)
    outline_color = hex_to_ass(style.outline_color)
    bold = -1 if style.bold else 0
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{font_name},{font_size},{primary},{primary},{outline_color},"
        f"{outline_color},{bold},0,0,0,100,100,0,0,1,{outline},0,2,"
        f"{margin_side},{margin_side},{margin_bottom},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for cue in cues:
        text = cue.text.replace("{", "(").replace("}", ")").replace("\n", "\\N")
        lines.append(
            f"Dialogue: 0,{ass_timestamp(cue.start_ms)},{ass_timestamp(cue.end_ms)},"
            f"Default,,0,0,0,,{text}"
        )
    return "\n".join(lines) + "\n"


def escape_filter_path(path: Path) -> str:
    """Escapa o caminho para o argumento do filtro do ffmpeg (`\\`, `'` e `:`)."""
    return str(path).replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")


def build_burn_command(
    ffmpeg: str,
    video: Path,
    ass_file: Path,
    fonts_dir: Path,
    output: Path,
    preset: str,
    crf: int,
) -> list[str]:
    """Monta o comando de queima como lista, nunca para shell (RNF-09)."""
    ass_filter = (
        f"ass=filename='{escape_filter_path(ass_file)}':fontsdir='{escape_filter_path(fonts_dir)}'"
    )
    return [
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video),
        "-vf",
        ass_filter,
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        str(output),
    ]


def check_libass(ffmpeg: str) -> None:
    """Confirma que o ffmpeg existe e tem o filtro `ass` (KNW-001)."""
    if shutil.which(ffmpeg) is None:
        raise DependencyMissingError(f"binário não encontrado: {ffmpeg}")
    try:
        proc = subprocess.run(
            [ffmpeg, "-hide_banner", "-filters"], capture_output=True, text=True, check=False
        )
    except OSError as exc:
        raise DependencyMissingError(f"não foi possível executar o ffmpeg: {exc}") from exc
    if not any(_ASS_FILTER_LINE.match(line) for line in proc.stdout.splitlines()):
        raise DependencyMissingError("ffmpeg sem libass; no server use o ffmpeg-full (KNW-001)")


def _run_ffmpeg(
    cmd: list[str], duration_s: float, on_progress: Callable[[float], None]
) -> tuple[int, str]:
    """Roda o ffmpeg lendo o progresso do stdout; devolve (código de saída, stderr)."""
    proc = subprocess.Popen(  # noqa: S603 - lista de argumentos, sem shell
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    stderr_parts: list[str] = []

    def _drain() -> None:
        if proc.stderr is not None:
            stderr_parts.append(proc.stderr.read())

    reader = threading.Thread(target=_drain, daemon=True)
    reader.start()
    if proc.stdout is not None:
        for raw in proc.stdout:
            key, _, value = raw.strip().partition("=")
            if key in ("out_time_us", "out_time_ms") and value.lstrip("-").isdigit():
                micros = int(value)
                if micros >= 0 and duration_s > 0:
                    on_progress(min(micros / 1e6 / duration_s, 0.99))
    code = proc.wait()
    reader.join()
    return code, "".join(stderr_parts)


def burn_cues(
    video: Path,
    cues: Sequence[Cue],
    output: Path,
    probe: ProbeResult,
    style: SubtitleStyle,
    burn: BurnSettings,
    font_path: Path,
    on_progress: Callable[[float], None],
) -> Path:
    """Queima as legendas no vídeo mantendo resolução, duração e áudio (RF-22)."""
    if not font_path.exists():
        raise DependencyMissingError(f"fonte não encontrada: {font_path}")
    check_libass(burn.ffmpeg)

    ass_file = output.with_name(f".{output.stem}.ass")
    part = output.with_name(f".{output.stem}.part.mp4")
    ass_file.write_text(cues_to_ass(cues, probe.width, probe.height, style), encoding="utf-8")

    def _cleanup() -> None:
        part.unlink(missing_ok=True)
        ass_file.unlink(missing_ok=True)

    cmd = build_burn_command(
        burn.ffmpeg, video, ass_file, font_path.parent, part, burn.preset, burn.crf
    )
    try:
        code, stderr = _run_ffmpeg(cmd, probe.duration_s, on_progress)
        if code != 0 and any(msg in stderr for msg in _AUDIO_CODEC_ERRORS):
            # Áudio original não cabe no MP4: reencoda só o áudio, uma única vez.
            part.unlink(missing_ok=True)
            idx = cmd.index("-c:a")
            retry = [*cmd[: idx + 1], "aac", "-b:a", "192k", *cmd[idx + 2 :]]
            code, stderr = _run_ffmpeg(retry, probe.duration_s, on_progress)
        if code != 0:
            _cleanup()
            if "No space left on device" in stderr:
                raise TranslunarError("sem espaço em disco")
            tail = "\n".join(stderr.strip().splitlines()[-5:])
            raise TranslunarError(f"falha na queima (ffmpeg código {code}): {tail}")
        os.replace(part, output)
    except BaseException:
        _cleanup()
        raise
    ass_file.unlink(missing_ok=True)
    on_progress(1.0)
    return output
