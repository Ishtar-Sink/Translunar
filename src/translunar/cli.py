"""Ponto de entrada da CLI `legendar`."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from translunar import __version__
from translunar.core.config import Settings, load_settings
from translunar.core.errors import TranslunarError, UsageError, ValidationFailedError
from translunar.core.models import VIDEO_EXTENSIONS
from translunar.core.pipeline import (
    list_clip_states,
    register_translation,
    run_burn,
    run_transcription,
    transcriber_for,
)
from translunar.core.state import clip_dir, load_state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="legendar",
        description="Translunar: legendas multilíngues para vídeo vertical.",
    )
    parser.add_argument("--version", action="version", version=f"legendar {__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="<comando>")
    # Cada subcomando registra o seu `handler` com set_defaults.
    json_help = "saída em JSON"
    transcribe = subparsers.add_parser("transcrever", help="transcreve vídeos de entrada/")
    transcribe.add_argument("videos", nargs="*", metavar="VIDEO", help="padrão: todos de entrada/")
    transcribe.add_argument("--forcar", action="store_true", help="refaz mesmo com pt.srt pronto")
    transcribe.add_argument("--json", action="store_true", help=json_help)
    transcribe.set_defaults(handler=_run_transcribe)
    validate = subparsers.add_parser("validar", help="valida e registra uma tradução")
    validate.add_argument("caminho", metavar="CAMINHO_SRT", help="saida/<corte>/<idioma>.srt")
    validate.add_argument("--json", action="store_true", help=json_help)
    validate.set_defaults(handler=_run_validate)
    burn = subparsers.add_parser("queimar", help="queima a legenda de um ou mais idiomas")
    burn.add_argument("corte", metavar="CORTE")
    burn.add_argument("idiomas", metavar="IDIOMAS", help="separados por vírgula (ex.: en,es)")
    burn.add_argument("--forcar", action="store_true", help="refaz mesmo com o vídeo pronto")
    burn.add_argument("--json", action="store_true", help=json_help)
    burn.set_defaults(handler=_run_burn)
    status = subparsers.add_parser("status", help="lista os cortes e seus estados")
    status.add_argument("corte", nargs="?", default=None, metavar="CORTE")
    status.add_argument("--json", action="store_true", help=json_help)
    status.set_defaults(handler=_run_status)
    panel = subparsers.add_parser("painel", help="sobe o painel web")
    panel.add_argument("--host", default=None, help="endereço de escuta (padrão: config.yaml)")
    panel.add_argument("--porta", type=int, default=None, help="porta (padrão: config.yaml)")
    panel.set_defaults(handler=_run_panel)
    return parser


def _emit(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _stderr_progress(label: str) -> Callable[[float], None]:
    """Progresso em `stderr`, uma linha a cada 10%."""
    last = -1

    def callback(value: float) -> None:
        nonlocal last
        step = int(value * 10)
        if step != last:
            last = step
            print(f"{label}: {step * 10}%", file=sys.stderr)

    return callback


def _result(error: BaseException | None, **fields: Any) -> dict[str, Any]:
    return {**fields, "erro": None if error is None else str(error)}


def _exit_code(errors: Sequence[BaseException]) -> int:
    return getattr(errors[0], "exit_code", 1) if errors else 0


def _print_results(results: list[dict[str, Any]], as_json: bool) -> None:
    if as_json:
        _emit({"resultados": results})
        return
    for item in results:
        label = item.get("idioma") or item["clip_id"]
        prefix = f"{item['clip_id']}/{label}" if item.get("idioma") else item["clip_id"]
        if item["erro"] is not None:
            print(f"{prefix}: erro: {item['erro']}")
        else:
            print(f"{prefix}: {item['estado']}")


def _videos_to_transcribe(settings: Settings, names: Sequence[str]) -> list[str]:
    if names:
        return [Path(name).stem for name in names]
    if not settings.input_dir.is_dir():
        return []
    return sorted(
        path.stem
        for path in settings.input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    )


def _run_transcribe(args: argparse.Namespace) -> int:
    settings = load_settings()
    results: list[dict[str, Any]] = []
    errors: list[BaseException] = []
    for clip_id in _videos_to_transcribe(settings, args.videos):
        skipped = False
        try:
            directory = clip_dir(settings.output_dir, clip_id)
            skipped = not args.forcar and (directory / "pt.srt").exists()
            progress = (lambda _v: None) if args.json else _stderr_progress(clip_id)
            state = run_transcription(
                settings,
                clip_id,
                transcriber_for(settings),
                force=args.forcar,
                on_progress=progress,
            )
            estado = "pulado" if skipped else str(state.transcription.state)
            results.append(_result(None, video=state.video, clip_id=clip_id, estado=estado))
        except Exception as error:  # a falha de um vídeo não interrompe os outros (RF-33)
            errors.append(error)
            results.append(_result(error, video=None, clip_id=clip_id, estado="erro"))
    _print_results(results, args.json)
    return _exit_code(errors)


def _run_validate(args: argparse.Namespace) -> int:
    settings = load_settings()
    path = Path(args.caminho)
    _, problems = register_translation(settings, path)
    ok = not problems
    if args.json:
        _emit(
            {
                "ok": ok,
                "file": str(path.resolve()),
                "language": path.resolve().stem,
                "problems": [problem.to_dict() for problem in problems],
            }
        )
    elif ok:
        print("ok")
    else:
        for problem in problems:
            where = f"id {problem.id} " if problem.id is not None else ""
            print(f"{where}{problem.kind}: {problem.detail}")
    return 0 if ok else ValidationFailedError.exit_code


def _run_burn(args: argparse.Namespace) -> int:
    settings = load_settings()
    languages = [lang.strip() for lang in args.idiomas.split(",") if lang.strip()]
    if not languages:
        raise UsageError("informe ao menos um idioma")
    results: list[dict[str, Any]] = []
    errors: list[BaseException] = []
    for language in languages:
        try:
            directory = clip_dir(settings.output_dir, args.corte)
            before = load_state(directory, args.corte, "").burns.get(language)
            stamp = before.updated_at if before else None
            progress = (
                (lambda _v: None) if args.json else _stderr_progress(f"{args.corte}/{language}")
            )
            state = run_burn(
                settings, args.corte, language, force=args.forcar, on_progress=progress
            )
            burn = state.burns[language]
            estado = (
                "pulado" if before is not None and burn.updated_at == stamp else str(burn.state)
            )
            results.append(
                _result(None, video=state.video, clip_id=args.corte, idioma=language, estado=estado)
            )
        except Exception as error:
            errors.append(error)
            results.append(
                _result(error, video=None, clip_id=args.corte, idioma=language, estado="erro")
            )
    _print_results(results, args.json)
    return _exit_code(errors)


def _run_status(args: argparse.Namespace) -> int:
    settings = load_settings()
    states = list_clip_states(settings, args.corte)
    items = [
        {
            "clip_id": state.clip_id,
            "video": state.video,
            "pt_srt": str((settings.output_dir / state.clip_id / "pt.srt").resolve()),
            "estado": state.to_dict(),
        }
        for state in states
    ]
    if args.json:
        _emit({"cortes": items})
        return 0
    if not items:
        print("nenhum corte")
        return 0
    print(f"{'CORTE':<24}{'TRANSCRIÇÃO':<16}TRADUÇÕES / QUEIMAS")
    for state in states:
        translations = ", ".join(f"{k}={v.state}" for k, v in state.translations.items())
        burns = ", ".join(f"{k}={v.state}" for k, v in state.burns.items())
        details = "; ".join(
            part for part in (translations, f"queima: {burns}" if burns else "") if part
        )
        print(f"{state.clip_id:<24}{state.transcription.state!s:<16}{details}")
    return 0


def _run_panel(args: argparse.Namespace) -> int:
    import uvicorn

    from translunar.panel.app import create_app

    settings = load_settings()
    uvicorn.run(
        create_app(settings),
        host=args.host or settings.panel.host,
        port=args.porta or settings.panel.port,
        proxy_headers=True,
        forwarded_allow_ips="127.0.0.1",
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    try:
        return int(args.handler(args))
    except TranslunarError as erro:
        print(erro, file=sys.stderr)
        return erro.exit_code


def run() -> None:
    """Entrada do script `legendar` instalado pelo pyproject."""
    sys.exit(main())
