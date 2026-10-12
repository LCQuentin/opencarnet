#!/usr/bin/env bash
# Télécharge un reel/post Instagram + ses métadonnées, puis génère :
#   <id>.mp4        vidéo
#   <id>.info.json  métadonnées (légende, auteur, date, hashtags)
#   <id>.m4a        audio extrait (pour transcription)
#   <id>_sheet.jpg  planche de frames contact-sheet (pour lecture visuelle/OCR)
#   <id>_frames/    frames individuelles (si --frames)
#
# Usage :
#   bash fetch_media.sh "<url>" ./work [--cookies CHEMIN_COOKIES] [--frames N]
#
# Les cookies (export Netscape du navigateur connecté) sont nécessaires pour
# beaucoup de reels. Sans eux, yt-dlp ne fonctionne que sur du contenu public.
set -euo pipefail

URL="${1:?usage: fetch_media.sh <url> <outdir> [--cookies f] [--frames N]}"
OUT="${2:?outdir manquant}"
shift 2 || true

COOKIES=""
NFRAMES=12
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cookies) COOKIES="$2"; shift 2 ;;
    --frames) NFRAMES="$2"; shift 2 ;;
    *) echo "option inconnue: $1" >&2; exit 2 ;;
  esac
done

for bin in yt-dlp ffmpeg; do
  command -v "$bin" >/dev/null 2>&1 || { echo "[!] '$bin' absent. brew install $bin" >&2; exit 1; }
done

mkdir -p "$OUT"
if [[ -n "$COOKIES" ]]; then COOKIE_ARGS=(--cookies "$COOKIES"); else COOKIE_ARGS=(); fi

# L'ID est demandé à yt-dlp lui-même (et non déduit du dernier info.json modifié,
# faux si le dossier est partagé et que l'item était déjà téléchargé).
IDFILE=$(mktemp)
trap 'rm -f "$IDFILE"' EXIT

echo "[*] yt-dlp : $URL"
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

ID=$(tail -n 1 "$IDFILE")
if [[ -z "$ID" || ! -f "$OUT/$ID.info.json" ]]; then
  echo "[!] échec : aucun info.json produit." >&2
  exit 1
fi

MP4=$(ls "$OUT/$ID".mp4 2>/dev/null || ls "$OUT/$ID".webm 2>/dev/null || true)
if [[ -n "$MP4" ]]; then
  echo "[*] audio -> $ID.m4a"
  ffmpeg -y -loglevel error -i "$MP4" -vn -ac 1 -ar 16000 "$OUT/$ID.m4a"

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
  echo "[!] pas de vidéo (post image/carrousel ?) — l'info.json et la miniature restent."
fi

echo "[ok] $OUT/$ID.*"
