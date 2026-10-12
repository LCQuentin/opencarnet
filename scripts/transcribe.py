#!/usr/bin/env python3
"""Transcrit un fichier audio en texte (reel Instagram -> transcript).

Ordre de préférence :
  1. faster-whisper (rapide, local)  -> pip install faster-whisper
  2. openai-whisper CLI (whisper)    -> pip install openai-whisper
Si aucun n'est présent, on sort en erreur avec les instructions.

Usage :
    python3 transcribe.py audio.m4a --out audio.txt [--model small] [--lang fr]

Le transcript est volontairement brut : on ne « nettoie » pas agressivement,
car les noms d'outils mal transcrits doivent rester visibles (et être recoupés
avec la lecture visuelle des frames) plutôt qu'inventés.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def try_faster_whisper(path: Path, model: str, lang: str | None) -> str | None:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception:
        return None
    m = WhisperModel(model, device="auto", compute_type="int8")
    segments, _ = m.transcribe(str(path), language=lang, vad_filter=True)
    return " ".join(seg.text.strip() for seg in segments).strip()


def try_whisper_cli(path: Path, model: str, lang: str | None) -> str | None:
    if not shutil.which("whisper"):
        return None
    outdir = path.parent
    cmd = ["whisper", str(path), "--model", model, "--output_format", "txt",
           "--output_dir", str(outdir), "--fp16", "False"]
    if lang:
        cmd += ["--language", lang]
    subprocess.run(cmd, check=True, capture_output=True)
    txt = path.with_suffix(".txt")
    return txt.read_text(encoding="utf-8") if txt.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("audio")
    ap.add_argument("--out", default=None)
    ap.add_argument("--model", default="small", help="tiny|base|small|medium|large-v3")
    ap.add_argument("--lang", default=None, help="ex. fr ; vide = auto")
    args = ap.parse_args()

    path = Path(args.audio).expanduser()
    if not path.exists():
        print(f"[!] introuvable : {path}", file=sys.stderr)
        return 1

    text = try_faster_whisper(path, args.model, args.lang)
    if text is None:
        text = try_whisper_cli(path, args.model, args.lang)
    if text is None:
        print(
            "[!] aucun moteur de transcription.\n"
            "    python3 -m pip install faster-whisper   (recommandé)\n"
            "    ou: python3 -m pip install openai-whisper",
            file=sys.stderr,
        )
        return 2

    out = Path(args.out).expanduser() if args.out else path.with_suffix(".txt")
    out.write_text(text + "\n", encoding="utf-8")
    print(f"[ok] transcript ({len(text)} car.) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
