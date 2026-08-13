"""Command line control — most importantly, the way out.

    autolockin panic     stop everything, unlock everything, stay off
    autolockin status    what mode am I in and what is currently locked
    autolockin disarm    back to "off", leave the daemon running
    autolockin arm       actually enforce (asks first)
    autolockin serve     run the daemon in the foreground
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from . import config, paths, recover, store


def _stop_service() -> str:
    """Best effort. If systemd isn't managing it, that's fine — say so and move on."""
    try:
        result = subprocess.run(
            ["systemctl", "--user", "stop", "autolockin"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"could not stop the service ({exc}) — kill it by hand if it's running"
    if result.returncode == 0:
        return "service stopped"
    return "service was not running under systemd (nothing to stop)"


def cmd_panic(_args: argparse.Namespace) -> int:
    """Disable enforcement, restore every locked folder, stop the daemon.

    Order matters: the PANIC file goes down *first*, so that even if the restore or
    the service stop goes wrong, a daemon that is somehow still alive will refuse to
    enforce anything on its next tick.
    """
    paths.ensure_dirs()
    paths.PANIC_FILE.write_text(
        "Autolockin enforcement is disabled while this file exists.\n"
        "Delete it, or run `autolockin arm`, to re-enable.\n",
        encoding="utf-8",
    )
    print(f"panic flag set: {paths.PANIC_FILE}")
    print("enforcement is now disabled\n")

    report = recover.restore_all()
    print("restoring folders:")
    print(recover.format_report(report))
    print()

    print(_stop_service())

    if not report.ok:
        print("\nSome folders could not be restored — use the chmod commands above.")
        return 1
    print("\nEverything is unlocked. You're free.")
    return 0


def cmd_status(_args: argparse.Namespace) -> int:
    mode = config.read_mode()
    panicked = config.is_panicked()

    print(f"mode:      {mode}{'  (forced off by panic flag)' if panicked else ''}")
    print(f"enforcing: {'yes' if config.should_enforce() else 'no'}")
    print(f"config:    {paths.CONFIG_FILE}")
    print(f"board:     {paths.BOARD_FILE}")

    ledger = store.load_ledger()
    if ledger:
        print(f"\ncurrently locked ({len(ledger)}):")
        for path, original in sorted(ledger.items()):
            print(f"  {path}  (restores to {original & 0o7777:o})")
        print("\nrun `autolockin panic` to unlock all of it")
    else:
        print("\nnothing is locked")

    board = store.load_board()
    print(f"\nboard: {len(board.tasks)} tasks, {len(board.rewards)} rewards")
    return 0


def cmd_restore(_args: argparse.Namespace) -> int:
    """Unlock everything, without touching the mode. This is the unit's ExecStop."""
    report = recover.restore_all()
    print(recover.format_report(report))
    return 0 if report.ok else 1


def cmd_disarm(_args: argparse.Namespace) -> int:
    config.write_mode("off")
    print("mode is now 'off' — the board still resolves, but nothing is enforced")
    report = recover.restore_all()
    print(recover.format_report(report))
    return 0 if report.ok else 1


def cmd_arm(args: argparse.Namespace) -> int:
    if not args.yes:
        print("Arming lets Autolockin chmod folders and kill processes for real.")
        print("Run it in 'dry-run' for a while first if you haven't.")
        answer = input("Type 'arm' to confirm: ").strip()
        if answer != "arm":
            print("cancelled")
            return 1
    paths.PANIC_FILE.unlink(missing_ok=True)
    config.write_mode("armed")
    print("mode is now 'armed'. `autolockin panic` undoes everything.")
    return 0


def cmd_dryrun(_args: argparse.Namespace) -> int:
    paths.PANIC_FILE.unlink(missing_ok=True)
    config.write_mode("dry-run")
    print(f"mode is now 'dry-run' — intentions will be logged to {paths.DRYRUN_LOG}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    config.ensure_config()
    uvicorn.run("autolockin.app:app", host=args.host, port=args.port, log_level="info")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autolockin", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("panic", help="unlock everything and stop enforcing (the way out)").set_defaults(
        func=cmd_panic
    )
    sub.add_parser("status", help="show mode and what is locked").set_defaults(func=cmd_status)
    sub.add_parser("restore", help="unlock everything, leave the mode alone").set_defaults(
        func=cmd_restore
    )
    sub.add_parser("disarm", help="set mode to off and unlock").set_defaults(func=cmd_disarm)
    sub.add_parser("dry-run", help="set mode to dry-run").set_defaults(func=cmd_dryrun)

    arm = sub.add_parser("arm", help="set mode to armed (enforces for real)")
    arm.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    arm.set_defaults(func=cmd_arm)

    serve = sub.add_parser("serve", help="run the daemon in the foreground")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8420)
    serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
