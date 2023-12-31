#!/usr/bin/bash

# This script shows some information about the input segment files using
# FFMPEG. The output is CSV formatted, and goes to stdout. The sequence number
# is taken out from the filename as a first number. The duration is determined
# after re-encoding with the null muxer.

# Usage: bash extract-ffmpeg-entries.sh SEGMENT_FILE...

echo "sequence,duration"

for path in "$@"; do
  sequence="$(basename "$path" | grep -oP '^\D*\K([0-9]+)')"
  if [[ -z "$sequence" ]]; then
    >&2 echo "error: Couldn't find a sequence number in the filename: ${path}"
    exit 1
  fi
  showed_entries="$(ffprobe -v error -of csv=p=0 \
    -show_entries format=duration \
    "$path")" || exit 1
  printf '%s,%s\n' "$sequence" "$showed_entries"
done
