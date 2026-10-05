#!/usr/bin/env bash
# Thin launcher: run the bundled `lk` CLI from anywhere.
#
# The bundle lives next to the installed skills, so resolve this script's real
# location (following symlinks) and delegate. Keeps `skills/*/SKILL.md` free of
# hard-coded absolute paths.
set -euo pipefail

src="${BASH_SOURCE[0]}"
while [ -L "$src" ]; do
  dir="$(cd -P "$(dirname "$src")" && pwd)"
  src="$(readlink "$src")"
  [[ "$src" != /* ]] && src="$dir/$src"
done
HERE="$(cd -P "$(dirname "$src")" && pwd)"

exec python "$HERE/lk.py" "$@"
