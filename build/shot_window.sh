#!/usr/bin/env bash
# Capture a screenshot of one application window on macOS.
#
# usage: build/shot_window.sh <app-process-name> <out.png> [settle-seconds]
#
# The window bounds come from System Events; `screencapture -R` then grabs that
# rectangle from the screen.  The app must be frontmost, so it is activated
# first.
set -uo pipefail

APP="$1"
OUT="$2"
SETTLE="${3:-3}"

bounds=$(osascript <<OSA
tell application "System Events"
  if not (exists process "$APP") then return "NOPROC"
  tell process "$APP"
    set frontmost to true
    delay 1
    if (count of windows) is 0 then return "NOWIN"
    set w to front window
    set p to position of w
    set s to size of w
    return ((item 1 of p) as text) & " " & ((item 2 of p) as text) & " " & ((item 1 of s) as text) & " " & ((item 2 of s) as text)
  end tell
end tell
OSA
)

if [ "$bounds" = "NOPROC" ] || [ "$bounds" = "NOWIN" ] || [ -z "$bounds" ]; then
  echo "shot_window: cannot read bounds for '$APP' ($bounds)" >&2
  exit 1
fi

read -r X Y W H <<<"$bounds"
echo "shot_window: $APP bounds x=$X y=$Y w=$W h=$H"
sleep "$SETTLE"
screencapture -x -R"$X,$Y,$W,$H" "$OUT"
if [ -s "$OUT" ]; then
  echo "shot_window: wrote $OUT ($(wc -c < "$OUT") bytes)"
else
  echo "shot_window: screencapture produced nothing" >&2
  exit 1
fi
