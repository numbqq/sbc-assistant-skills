# Control Protocol

The running launcher listens on `VIBE_CONTROL_SOCKET` or `XDG_RUNTIME_DIR/vibe-control.sock`.

Use `/home/khadas/v5-block-example/runtime/control-app` when the agent is not already running from `/home/khadas/v5-block-example`.

## Commands

```bash
runtime/control-app catalog
runtime/control-app list
runtime/control-app status
runtime/control-app start <app_id>
runtime/control-app stop
runtime/control-app generate --backend picoclaw --prompt "<prompt>"
```

## Catalog shape

The catalog response is JSON and includes the discovered apps:

```json
{
  "ok": true,
  "action": "list",
  "count": 2,
  "apps": [
    {
      "id": "gsensor-ball",
      "name": "G-Sensor Ball",
      "description": "...",
      "aliases": ["gsensor", "g-sensor", "g-sensor ball"],
      "entrypoint": "main.py"
    }
  ]
}
```

## Resolution order

1. exact `id`
2. exact `name`
3. returned `aliases`
4. ask if still ambiguous

For requests like "gsensor 小球" or "打开小球应用", do not assume a file path. Read the catalog, then prefer the app whose `id` is `gsensor-ball` when the catalog confirms that match.

## Generation flow

Use `runtime/control-app generate` when the user wants a new app or a new variant. Use `--backend picoclaw` for real dynamic generation. Use `--backend mock` only for local smoke testing when explicitly requested. `VIBE_PICOCLAW_COMMAND` can override the built-in Picoclaw adapter.

The control socket reply only confirms that generation started. After the backend finishes, the launcher refreshes the catalog and auto-starts the new app if generation succeeded.

Example:

```json
{"ok": true, "action": "generate", "backend": "picoclaw", "prompt": "做一个会动的小球"}
```

## Operating rules

- Control the running launcher only.
- Do not execute app scripts directly.
- Do not start a second `run-ui` instance if one is already active.
- For `gsensor-ball`, prefer the canonical ID returned by the catalog, not a guessed script path.
