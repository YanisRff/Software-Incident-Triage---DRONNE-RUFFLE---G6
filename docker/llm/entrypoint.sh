#!/bin/sh
set -e
lms daemon up
lms server start --bind 0.0.0.0 --port 1234
if ! lms ls | grep -qi "$LLM_MODEL"; then
  lms get "$LLM_MODEL" -y
fi
lms load "$LLM_MODEL" --gpu off --identifier "$LLM_MODEL" -y
echo "LM Studio ready: $LLM_MODEL on :1234"
exec tail -f /dev/null
