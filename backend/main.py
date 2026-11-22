"""Aplikasi FastAPI MedDrop: route API dan penyajian frontend statis.

Jalankan dari root proyek:
    python -m backend.main
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.config import ROOT_DIR, load_config

APP_NAME = "MedDrop"
FRONTEND_DIR = ROOT_DIR / "frontend"


def create_app(config: dict | None = None) -> FastAPI:
    cfg = config if config is not None else load_config()
    app = FastAPI(title="MedDrop API", description="Prototipe simulasi. Bukan alat medis.")
    app.state.config = cfg

    @app.get("/api/config")
    def get_config():
        clf = cfg["classifier"]
        return {
            "app_name": APP_NAME,
            "classifier": {
                "backend": clf["backend"],
                "is_mock": clf["backend"] == "mock",
                "threshold_with_barcode": clf["threshold_with_barcode"],
                "threshold_photo_only": clf["threshold_photo_only"],
                "min_confidence_floor": clf["min_confidence_floor"],
            },
            "weight": cfg["weight"],
            "points": cfg["points"],
            "bin": cfg["bin"],
        }

    # Dipasang terakhir agar route /api/* di atas tetap didahulukan.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000)
