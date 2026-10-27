#!/usr/bin/env bash
# Install binaries from a GitHub release tarball that publishes a sibling
# "<tarball>.sha256" file (the astral-sh uv/ruff convention), verifying the
# checksum before anything is installed.
#
#   install-release-binary.sh <tarball_url> <dest_dir> <binary>...
set -euo pipefail

[ $# -ge 3 ] || { echo "Usage: $0 <tarball_url> <dest_dir> <binary>..." >&2; exit 2; }
URL="$1"
DEST_DIR="$2"
shift 2
NAME="$(basename "$URL")"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo ">>> Downloading $NAME..."
curl -fsSL --retry 3 -o "$TMP/$NAME" "$URL"
curl -fsSL --retry 3 -o "$TMP/$NAME.sha256" "$URL.sha256"

EXPECTED="$(awk '{ print $1; exit }' "$TMP/$NAME.sha256")"
ACTUAL="$(sha256sum "$TMP/$NAME" | awk '{ print $1 }')"
if [ -z "$EXPECTED" ] || [ "$ACTUAL" != "$EXPECTED" ]; then
  echo "Error: SHA-256 mismatch for $NAME (expected '$EXPECTED', got '$ACTUAL')" >&2
  exit 1
fi
echo "    sha256 ok: $ACTUAL"

mkdir -p "$TMP/x" "$DEST_DIR"
tar -xzf "$TMP/$NAME" -C "$TMP/x"
for bin in "$@"; do
  src="$(find "$TMP/x" -type f -name "$bin" | head -1)"
  [ -n "$src" ] || { echo "Error: $bin not found in $NAME" >&2; exit 1; }
  install -m 0755 "$src" "$DEST_DIR/$bin"
  echo "    installed $DEST_DIR/$bin"
done
