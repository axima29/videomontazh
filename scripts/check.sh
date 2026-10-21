#!/bin/zsh
# Проверка готового ролика до сдачи: длительность, громкость (цель -14 LUFS), лист кадров по каждой секунде.
# ./check.sh "<ролик>.mp4"  -> рядом "<ролик> - лист кадров.png" (8 кадров в ряд, кадр на секунду). Лист смотреть глазами весь.
set -e
F=$1; FF=${FFMPEG:-ffmpeg}; FP=${FFPROBE:-ffprobe}
D=$($FP -v error -show_entries format=duration -of csv=p=0 "$F")
echo "длительность: $D c"
$FF -hide_banner -nostats -i "$F" -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I|Peak):" | sed 's/^ */громкость /'
N=$(python3 -c "import math; print(math.ceil($D / 8))")
$FF -v error -y -i "$F" -vf "fps=1,scale=270:-1,tile=8x$N:padding=6:color=white" -frames:v 1 "${F:r} - лист кадров.png"
echo "лист кадров: ${F:r} - лист кадров.png"
