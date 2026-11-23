"""Start DesignLab: API + built frontend on http://127.0.0.1:8640, then open the browser.

    python run.py            # normal start
    python run.py --no-browser
"""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser

HOST, PORT = "127.0.0.1", 8640
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def main() -> None:
    try:
        import uvicorn  # noqa: F401
        import fastapi  # noqa: F401
        import scipy  # noqa: F401
        import statsmodels  # noqa: F401
    except ImportError as e:
        print(f"Missing dependency: {e.name}. Run:  pip install -r requirements.txt")
        sys.exit(1)
    if not os.path.isfile(os.path.join(ROOT, "web", "dist", "index.html")):
        print("The web interface is not built yet. Run:  cd web && npm ci && npm run build")
        print("(The API still starts; its docs are at http://127.0.0.1:8640/docs)")
    url = f"http://{HOST}:{PORT}"
    if "--no-browser" not in sys.argv:
        threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(url)), daemon=True).start()
    print(f"DesignLab is running at {url}  (Ctrl+C to stop)")
    import uvicorn
    uvicorn.run("api.main:app", host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
