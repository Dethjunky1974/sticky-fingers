#!/bin/zsh
# Restart the Claude pane relay. Safe to call from inside a pane session: the new
# relay is launched detached first and binds 9240 as soon as the old one exits.
cd "$(dirname "$0")"
OLD=$(lsof -tnP -iTCP:9240 -sTCP:LISTEN)
nohup zsh -c 'while lsof -tnP -iTCP:9240 -sTCP:LISTEN >/dev/null; do sleep 0.2; done; exec node relay.mjs' >/dev/null 2>&1 &
disown
[[ -n "$OLD" ]] && kill $OLD
