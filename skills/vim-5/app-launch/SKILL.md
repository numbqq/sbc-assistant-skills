---
name: khadas-vim-5-app-launch
description: Use when you need to open, close, identify, or request generation of VIM 5 launcher apps from natural language through runtime/control-app. Do not use when an internal app generator is already writing app files.
---

# VIM 5 App Launch

## Overview

Use this skill when the request is to start, stop, identify, or request generation of a VIM 5 app such as `gsensor-ball`, `bouncing-ball`, or a new generated app. The launcher and its control socket are the source of truth. Do not restart `run-ui` if it is already running, and do not call `python3 apps/<app-id>/main.py` directly.

Repository path on the target board is `/home/khadas/v5-block-example`. If the current working directory is not that repository, run `/home/khadas/v5-block-example/runtime/control-app ...` instead of a relative `runtime/control-app ...` command.

## Workflow

1. For requests to create or regenerate an app, run `runtime/control-app generate --backend picoclaw --prompt "<user request>"`. The launcher owns the loading UI and auto-starts the generated app after success.
2. Use `mock` only for local smoke testing when explicitly requested.
3. For requests to open an existing app, read the app catalog first with `runtime/control-app catalog`, resolve the request to a canonical `app_id`, then run `runtime/control-app start <app_id>`.
4. Stop the current app with `runtime/control-app stop`.
5. If the catalog does not give a confident match, ask a clarification question instead of guessing.
6. If the control socket is unavailable, tell the user to start `run-ui` first.

## Matching rules

- Treat the catalog as authoritative.
- Prefer exact `app_id` matches over exact name matches.
- Use aliases only when the catalog returns them.
- `generated-demo` is the generated output slot, not a normal app shortcut for creation requests. Never satisfy a "create/make/generate/build/develop/modify an app" request by running `runtime/control-app start generated-demo`; use `runtime/control-app generate --backend picoclaw --prompt "<user request>"` instead.
- Never invent a command path, never spawn the Python entrypoint directly, and never launch `run-ui` a second time from this skill.
- If `VIBE_PICOCLAW_INTERNAL_GENERATION=1`, do not call `runtime/control-app`; follow the generator prompt and write files directly under the requested app directory.

## Generation notes

- `generate` is asynchronous: it tells the launcher to invoke the backend, then the launcher refreshes apps and auto-starts the generated app when generation finishes.
- For the real backend, the launcher runs `runtime/generate-app --backend picoclaw`, which uses the Picoclaw adapter unless `VIBE_PICOCLAW_COMMAND` overrides it.
- The backend command should read a JSON request from stdin and print JSON with at least `ok` and `app_id` to stdout.
- Generated Python/Pygame apps must use `pygame.display.set_mode((0, 0), pygame.FULLSCREEN)` when possible. If a fixed logical canvas is used, it must still be presented fullscreen through the platform runtime; do not create small top-left windows.

## Examples

- `open gsensor ball app` -> `catalog`, resolve to `gsensor-ball`, then `start gsensor-ball`
- `close the current app` -> `stop`
- `make a new animated ball app` -> `generate --backend picoclaw --prompt "make a new animated ball app"`
- `做一个飞翔的小鸟` -> `generate --backend picoclaw --prompt "做一个飞翔的小鸟"`
- `重新生成一个贪吃蛇应用` -> `generate --backend picoclaw --prompt "重新生成一个贪吃蛇应用"`

## See also

- [Control protocol](references/control-protocol.md)
