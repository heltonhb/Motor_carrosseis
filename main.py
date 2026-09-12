"""
main.py — Entry point para execução direta via `uv run python main.py`
ou `python main.py`. Inicia o servidor Streamlit programaticamente.
"""

import subprocess
import sys


def main() -> None:
    """Inicia o app Streamlit."""
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless", "true"],
        check=True,
    )


if __name__ == "__main__":
    main()
