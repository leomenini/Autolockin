# Autolockin — working notes

An n8n-style flowchart of the user's tasks and homework. Each node is a task with a time
estimate, deadline and resource links; edges are prerequisites; reward nodes at the end of a
chain gate a folder or a game.

Not a git repo. Linux Mint 22.3 / Cinnamon, Python 3.12, Node 20.

## The two constraints that shape everything

1. **Build one touches nothing on the machine.** Enforcement is gated behind a single
   `config.should_enforce()` call and ships `mode = "off"`. No `chmod`, no process
   inspection, no kills. `tests/test_api.py::test_daemon_is_inert` asserts this and must
   keep passing.
2. **The escape hatch was built before anything that could lock.** `autolockin panic` must
   always work, including when the daemon is hung or crashed — which is why
   `autolockin/recover.py` reads `locks.json` directly and imports nothing from the daemon.

The user asked for both of these explicitly after seeing the first plan. Don't quietly
relax either one.

## Layout

```
autolockin/
  models.py    Board / TaskNode / RewardNode / Edge / BoardState (pydantic)
  graph.py     resolution — pure, no I/O, the heart of the thing
  store.py     atomic JSON writes for board.json and locks.json
  config.py    mode flag; every failure path falls back to "off"
  recover.py   ledger-direct restore; depends on nothing else
  cli.py       panic / status / restore / disarm / dry-run / arm / serve
  ticker.py    5s loop: advance recurrence -> resolve -> (enforce) -> broadcast
  app.py       FastAPI routes + /ws + serves frontend/dist
frontend/      Vite + React + @xyflow/react v12
install/       systemd --user unit
tests/         test_graph.py, test_recover.py, test_api.py  (36 passing)
```

State: `~/.local/share/autolockin/{board.json,locks.json,PANIC}`,
config: `~/.config/autolockin/config.toml`.

## Design decisions already made (don't relitigate)

- **Lock strength: speed bump.** `chmod 000` + process watchdog. `sudo` defeats it; that is
  the point. No encryption, so recovery is always possible.
- **Unlock granularity: per-reward node**, resolved through the full transitive ancestor set.
- **Reset: per-node deadlines**, not a daily cron. A repeating task flips back to `todo` when
  its deadline passes, which re-locks anything downstream. `advance_recurrence` in
  `graph.py` is the only reset mechanism.
- **Authoring: drag-and-drop** on the canvas, not a YAML file.

## Current state

Build one is complete and verified: canvas authoring (add/drag/connect/delete/edit) persists,
status cycling works, rewards flip 🔒/🔓 live over the WebSocket, deadlines re-lock.

The service is **stopped and disabled** — it does not start at login. Start it deliberately
(see README).

## Next steps — build two, "teeth"

Only after the user has lived with build one and wants it.

1. `locks.py` — folder lock/unlock via chmod, writing `locks.json` *before* any chmod.
   Safety rules to enforce before touching anything: resolved path strictly inside `$HOME`;
   hard denylist on `$HOME` itself, `~/.config`, `~/.local`, `~/.cache`, `~/.ssh`, the
   project dir, and top-level dotfile dirs; must be an existing directory. Refuse loudly and
   surface the error in the UI rather than skipping silently.
   On daemon startup: restore the whole ledger *first*, then re-apply from a fresh resolve,
   so a crash mid-lock can't strand a folder at `000`.
2. `watchdog.py` — walk `/proc/*/cmdline` (stdlib, no psutil) matching patterns from locked
   rewards. SIGTERM, then SIGKILL after 3s. Never PID 1, never processes of another uid.
   `notify-send` naming the blocking task titles, rate-limited to once per 30s per reward.
3. Wire both into `ticker._enforce`, which is currently a documented no-op.
4. `dry-run` must be genuinely implemented in both — log the intended action to
   `dryrun.log` and return before the syscall. This is how the user will validate their
   folder paths and process patterns before arming.
5. Tests: `tests/test_locks.py` against `tmp_path`, with the denylist tested explicitly, and
   a kill-switch-under-load test (lock a real temp dir, SIGSTOP the daemon, confirm
   `autolockin panic` still restores it).

Arming order for the user: `dry-run` for a week → read `dryrun.log` → `autolockin arm`.

## Gotchas hit already

- **React Flow re-render loop.** Feeding `dimensions`/`select` changes back into board state
  regenerates the node array and emits more changes forever. `onNodesChange` in `App.tsx`
  now handles only `position` and `remove` and returns early otherwise. Keep it that way.
- `pkill -f "autolockin serve"` matches its own command line and kills the calling shell.
  Use `systemctl --user stop autolockin`, or a bracketed pattern.
- Firefox `--headless --screenshot` fires before React finishes fetching, producing an empty
  canvas. Playwright (installed in `.venv`) with `wait_until="networkidle"` works; click
  `[data-id='<id>'] .body`, not the React Flow node wrapper.
- `npm audit` flags two dev-server advisories (esbuild/vite). Build output is unaffected.

## Verifying changes

```bash
.venv/bin/python -m pytest              # 36 tests
cd frontend && npx tsc --noEmit && npm run build
```

For UI changes, actually drive it: start the daemon, then use Playwright from `.venv` to
click through and assert against `/api/board`. Scratch scripts from the first session
(`seed.py`, `shot.py`, `interact.py`, `edge.py`) were in the session scratchpad and are gone;
rewrite as needed — they were ~30 lines each.
