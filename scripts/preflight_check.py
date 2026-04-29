#!/usr/bin/env python3
import argparse
import importlib.util
import pathlib
import sys


REQUIRED_FILES = [
    "run.py",
    "config.py",
    "app/__init__.py",
    "app/models/__init__.py",
    "app/models/user.py",
    "app/models/bikelane.py",
    "app/routes/__init__.py",
    "app/routes/auth.py",
    "app/routes/main.py",
    "app/routes/public.py",
    "app/utils/__init__.py",
    "app/utils/file_handler.py",
    "app/utils/validators.py",
]


def fail(message):
    print(f"PRECHECK FAILED: {message}", file=sys.stderr)
    raise SystemExit(1)


def check_required_files(root):
    missing = [path for path in REQUIRED_FILES if not (root / path).is_file()]
    if missing:
        fail("Missing required files: " + ", ".join(missing))


def check_appledouble(root):
    junk = sorted(str(path.relative_to(root)) for path in root.rglob("._*"))
    if junk:
        fail("AppleDouble files must not be deployed: " + ", ".join(junk))


def import_run_module(root):
    run_path = root / "run.py"
    spec = importlib.util.spec_from_file_location("velojol_run", run_path)
    if spec is None or spec.loader is None:
        fail("Unable to create import spec for run.py")

    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(root))
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover - runtime guard
        fail(f"Application import failed: {exc}")
    finally:
        if sys.path and sys.path[0] == str(root):
            sys.path.pop(0)

    if not getattr(module, "app", None):
        fail("run.py did not expose app")


def main():
    parser = argparse.ArgumentParser(description="Validate a release before deployment.")
    parser.add_argument("root", nargs="?", default=".", help="Release directory to validate")
    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()
    check_required_files(root)
    check_appledouble(root)
    import_run_module(root)
    print(f"PRECHECK OK: {root}")


if __name__ == "__main__":
    main()
