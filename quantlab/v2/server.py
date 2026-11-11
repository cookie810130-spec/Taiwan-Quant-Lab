"""Local-only launch; create stable private API key for first run."""
import os
from pathlib import Path
import secrets
import sys


def configure_key():
    if os.environ.get("QUANTLAB_API_KEY"):
        if len(os.environ["QUANTLAB_API_KEY"]) < 24:
            raise RuntimeError("QUANTLAB_API_KEY must have at least 24 characters.")
        return "environment variable"
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "TaiwanQuantLab"
    base.mkdir(parents=True, exist_ok=True)
    key_path = base / "api_key.txt"
    if not key_path.exists():
        # Exclusive creation avoids clobbering an existing key.
        with key_path.open("x", encoding="utf-8") as fh:
            fh.write(secrets.token_urlsafe(32))
    key = key_path.read_text(encoding="utf-8").strip()
    if len(key) < 24:
        raise RuntimeError("Stored API key is unexpectedly short.")
    os.environ["QUANTLAB_API_KEY"] = key
    return str(key_path)


def main():
    import uvicorn
    location = configure_key()
    print("Taiwan-Quant-Lab V2 backend: http://127.0.0.1:8000")
    print("API key location (keep PRIVATE):", location)
    print("For Android use Tailscale Serve HTTPS. Do NOT port-forward 8000.")
    uvicorn.run("quantlab.v2.api:app", host="127.0.0.1", port=8000,
                workers=1, access_log=False)


if __name__ == "__main__":
    main()
