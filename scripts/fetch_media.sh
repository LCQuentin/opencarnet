#!/usr/bin/env bash
# Télécharge un item (Instagram, TikTok, YouTube…) + ses métadonnées, puis génère :
#   <id>.info.json  métadonnées (titre, auteur, date, description, sous-titres dispo)
#   <id>.mp4        vidéo                       (sauf --subs)
#   <id>.m4a        audio extrait (transcription)   (sauf --subs)
#   <id>_sheet.jpg  planche de frames (lecture visuelle)  (sauf --subs / --no-frames)
#   <id>_frames/    frames individuelles            (sauf --subs / --no-frames)
#   <id>.txt        transcript issu des sous-titres (mode --subs)
#
# Usage :
#   bash fetch_media.sh "<url>" ./work [--cookies CHEMIN] [--frames N] [--subs] [--no-frames] [--sub-langs LISTE]
#
# --subs : vidéos longues (YouTube…) — ne télécharge pas la vidéo : récupère les
#          sous-titres (auto ou manuels) et écrit <id>.txt. Évite Whisper.
# --no-frames : télécharge la vidéo mais saute la planche de frames.
# --sub-langs : langues de sous-titres pour --subs (défaut "en.*,fr.*" ; "all,-live_chat"
#          pour tout prendre).
#
# Les cookies (export Netscape du navigateur connecté) sont nécessaires pour
# beaucoup de reels Instagram. Sans eux, yt-dlp ne fonctionne que sur du public.
set -euo pipefail

URL="${1:?usage: fetch_media.sh <url> <outdir> [--cookies f] [--frames N] [--subs] [--no-frames] [--sub-langs L]}"
OUT="${2:?outdir manquant}"
shift 2 || true

COOKIES=""
NFRAMES=12
SUBS=0
SUBLANGS="${OPENCARNET_SUB_LANGS:-en.*,fr.*}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cookies) COOKIES="$2"; shift 2 ;;
    --frames) NFRAMES="$2"; shift 2 ;;
    --subs) SUBS=1; shift ;;
    --no-frames) NFRAMES=0; shift ;;
    --sub-langs) SUBLANGS="$2"; shift 2 ;;
    *) echo "option inconnue: $1" >&2; exit 2 ;;
  esac
done

for bin in yt-dlp ffmpeg; do
  command -v "$bin" >/dev/null 2>&1 || { echo "[!] '$bin' absent. macOS : brew install $bin · Linux : sudo apt install $bin (ou pipx install yt-dlp)" >&2; exit 1; }
done

mkdir -p "$OUT"
if [[ -n "$COOKIES" ]]; then COOKIE_ARGS=(--cookies "$COOKIES"); else COOKIE_ARGS=(); fi

# L'ID est demandé à yt-dlp lui-même (et non déduit du dernier info.json modifié,
# faux si le dossier est partagé et que l'item était déjà téléchargé).
IDFILE=$(mktemp)
trap 'rm -f "$IDFILE"' EXIT

echo "[*] yt-dlp : $URL"
if [[ "$SUBS" == "1" ]]; then
  yt-dlp \
    ${COOKIE_ARGS[@]+"${COOKIE_ARGS[@]}"} \
    --no-playlist \
    --skip-download \
    --write-info-json --write-thumbnail \
    --write-subs --write-auto-subs --sub-langs "$SUBLANGS" --convert-subs srt \
    --print-to-file id "$IDFILE" \
    -o "$OUT/%(id)s.%(ext)s" \
    "$URL"
else
  yt-dlp \
    ${COOKIE_ARGS[@]+"${COOKIE_ARGS[@]}"} \
    --no-playlist \
    --no-simulate --print-to-file id "$IDFILE" \
    --ignore-no-formats-error \
    --write-info-json \
    --write-thumbnail \
    -f "bv*+ba/b" --merge-output-format mp4 \
    -o "$OUT/%(id)s.%(ext)s" \
    "$URL"
fi

ID=$(tail -n 1 "$IDFILE")
if [[ -z "$ID" || ! -f "$OUT/$ID.info.json" ]]; then
  echo "[!] échec : aucun info.json produit." >&2
  exit 1
fi

if [[ "$SUBS" == "1" ]]; then
  SRT=$(ls "$OUT/$ID".*.srt 2>/dev/null | head -n 1 || true)
  if [[ -z "$SRT" ]]; then
    echo "[!] aucun sous-titre pour $ID — relancer sans --subs (Whisper)." >&2
  else
    echo "[*] sous-titres -> $ID.txt ($(basename "$SRT"))"
    python3 - "$SRT" "$OUT/$ID.txt" <<'PY'
import re, sys
src, dst = sys.argv[1], sys.argv[2]
out, last = [], None
for line in open(src, encoding="utf-8", errors="replace"):
    s = line.rstrip("\n")
    if not s or "-->" in s or s.strip().isdigit():
        continue
    s = re.sub(r"<[^>]+>", "", s).strip()   # balises de style
    if s and s != last:
        out.append(s)
        last = s
open(dst, "w", encoding="utf-8").write("\n".join(out) + "\n")
PY
  fi
  echo "[ok] $OUT/$ID.*"
  exit 0
fi

MP4=$(ls "$OUT/$ID".mp4 2>/dev/null || ls "$OUT/$ID".webm 2>/dev/null || true)
if [[ -n "$MP4" ]]; then
  echo "[*] audio -> $ID.m4a"
  ffmpeg -y -loglevel error -i "$MP4" -vn -ac 1 -ar 16000 "$OUT/$ID.m4a"

  if [[ "$NFRAMES" -gt 0 ]]; then
    DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$MP4" 2>/dev/null || echo 0)
    STEP=$(python3 - "$DUR" "$NFRAMES" <<'PY'
import sys
dur=float(sys.argv[1] or 0); n=int(sys.argv[2])
print(max(dur/ max(n,1), 0.5))
PY
)
    echo "[*] frames (1 / ${STEP}s) -> ${ID}_frames/ + ${ID}_sheet.jpg"
    mkdir -p "$OUT/${ID}_frames"
    ffmpeg -y -loglevel error -i "$MP4" -vf "fps=1/${STEP},scale=480:-1" "$OUT/${ID}_frames/f_%03d.jpg"
    ffmpeg -y -loglevel error -i "$MP4" -vf "fps=1/${STEP},scale=360:-1,tile=4x3" -frames:v 1 "$OUT/${ID}_sheet.jpg"
  else
    echo "[*] frames ignorées (--no-frames)"
  fi
else
  echo "[!] pas de vidéo (post image/carrousel ?) — l'info.json et la miniature restent."
fi

echo "[ok] $OUT/$ID.*"
