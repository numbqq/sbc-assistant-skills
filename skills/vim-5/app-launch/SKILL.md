---
name: khadas-vim-5-app-launch
description: Use when you need to open, close, or identify VIM 5 apps from natural language, resolve canonical app IDs from the launcher catalog, or control the running product UI through the local socket instead of launching Python apps directly.
---

# VIM 5 App Launch

## Overview

Use this skill when the request is to start, stop, or identify a VIM 5 app such as `gsensor-ball`, `bouncing-ball`, or a generated app. The launcher and its control socket are the source of truth. Do not restart `run-ui` if it is already running, and do not call `python3 apps/<app-id>/main.py` directly.

## Workflow

1. Read the app catalog first with `runtime/control-app catalog`.
2. Resolve the request to a canonical `app_id` using exact ID first, then name, then aliases from the catalog.
3. Start the app with `runtime/control-app start <app_id>`.
4. Stop the current app with `runtime/control-app stop`.
5. If the catalog does not give a confident match, ask a clarification question instead of guessing.
6. If the control socket is unavailable, tell the user to start `run-ui` first.

## Matching rules

- Treat the catalog as authoritative.
- Prefer exact `app_id` matches over exact name matches.
- Use aliases only when the catalog returns them.
- Never invent a command path, never spawn the Python entrypoint directly, and never launch `run-ui` a second time from this skill.

## Examples

- `open gsensor ball app` -> `catalog`, resolve to `gsensor-ball`, then `start gsensor-ball`
- `close the current app` -> `stop`
- `open ball` -> consult the catalog first, then decide whether `gsensor-ball`, `bouncing-ball`, or another app is intended

## See also

- [Control protocol](references/control-protocol.md)
