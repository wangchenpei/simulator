from __future__ import annotations

import sys
from pathlib import Path


from bxsimulator.paths import project_root


def streamlit_app_path() -> Path:
    root = project_root()
    app = root / "app" / "streamlit_app.py"
    if not app.exists():
        raise FileNotFoundError(f"Streamlit app not found: {app}")
    return app


def main(argv: list[str] | None = None) -> int:
    try:
        import streamlit.web.cli as stcli
    except ImportError:
        print('Streamlit not installed. Run: pip install -e ".[ui]"', file=sys.stderr)
        return 1

    app = streamlit_app_path()
    extra = list(argv) if argv is not None else sys.argv[1:]
    sys.argv = ["streamlit", "run", str(app), *extra]
    stcli.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
