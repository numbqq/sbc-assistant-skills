---
name: khadas-vim-5-app-launch
description: Use when you need to open, close, identify, or generate VIM 5 apps from natural language, resolve canonical app IDs from the launcher catalog, or control the running product UI through the local socket instead of launching Python apps directly.
---

# VIM 5 App Launch

## Overview

Use this skill when the request is to start, stop, identify, or generate a VIM 5 app such as `gsensor-ball`, `bouncing-ball`, or a new generated app. The launcher and its control socket are the source of truth. Do not restart `run-ui` if it is already running, and do not call `python3 apps/<app-id>/main.py` directly.

Repository path on the target board is `/home/khadas/v5-block-example`. If the current working directory is not that repository, run `/home/khadas/v5-block-example/runtime/control-app ...` instead of a relative `runtime/control-app ...` command.

## Workflow

1. Read the app catalog first with `runtime/control-app catalog`.
2. If the request is to create a new app or a new variant, use `runtime/control-app generate --backend picoclaw --prompt "<user request>"`.
3. Use `mock` only for local smoke testing when explicitly requested.
4. If the request is to open an existing app, resolve the request to a canonical `app_id` using exact ID first, then name, then aliases from the catalog.
5. Start the app with `runtime/control-app start <app_id>`.
6. Stop the current app with `runtime/control-app stop`.
7. If the catalog does not give a confident match, ask a clarification question instead of guessing.
8. If the control socket is unavailable, tell the user to start `run-ui` first.

## Matching rules

- Treat the catalog as authoritative.
- Prefer exact `app_id` matches over exact name matches.
- Use aliases only when the catalog returns them.
- Never invent a command path, never spawn the Python entrypoint directly, and never launch `run-ui` a second time from this skill.

## Generation notes

- `generate` is asynchronous: it tells the launcher to invoke the backend, then the launcher refreshes apps and auto-starts the generated app when generation finishes.
- For the real backend, the launcher runs `runtime/generate-app --backend picoclaw`, which uses the Picoclaw adapter unless `VIBE_PICOCLAW_COMMAND` overrides it.
- The backend command should read a JSON request from stdin and print JSON with at least `ok` and `app_id` to stdout.

## Examples

- `open gsensor ball app` -> `catalog`, resolve to `gsensor-ball`, then `start gsensor-ball`
- `close the current app` -> `stop`
- `make a new animated ball app` -> `generate --backend picoclaw --prompt "make a new animated ball app"`

## See also

- [Control protocol](references/control-protocol.md)
