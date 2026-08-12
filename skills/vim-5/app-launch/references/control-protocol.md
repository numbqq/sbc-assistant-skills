# Control Protocol

The running launcher listens on `VIBE_CONTROL_SOCKET` or `XDG_RUNTIME_DIR/vibe-control.sock`.

## Commands

```bash
runtime/control-app catalog
runtime/control-app list
runtime/control-app status
runtime/control-app start <app_id>
runtime/control-app stop
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

## Operating rules

- Control the running launcher only.
- Do not execute app scripts directly.
- Do not start a second `run-ui` instance if one is already active.
- For `gsensor-ball`, prefer the canonical ID returned by the catalog, not a guessed script path.
