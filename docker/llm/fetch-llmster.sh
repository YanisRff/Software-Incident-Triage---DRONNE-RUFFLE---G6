#!/bin/sh
# Download the pinned llmster (LM Studio headless) bundle next to this script,
# resumable, and verify its sha512. Run once before building the llm image.
set -eu
VERSION="${LLMSTER_VERSION:-0.0.25-1}"
NAME="$VERSION-linux-x64.full.tar.gz"
URL="https://llmster.lmstudio.ai/download"
cd "$(dirname "$0")"
curl -fL --retry 20 --retry-all-errors -C - -o llmster.tar.gz "$URL/$NAME"
curl -fsSL "$URL/$VERSION-linux-x64.full.sha512" -o llmster.sha512 || true
if [ -s llmster.sha512 ]; then
  echo "$(cut -d' ' -f1 llmster.sha512)  llmster.tar.gz" | sha512sum -c -
fi
