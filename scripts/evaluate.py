"""Evaluasi model asli pada split test.

    python scripts/evaluate.py

Menghitung akurasi, precision/recall per kelas, confusion matrix, dan False Accept Rate
(barang yang seharusnya ditolak tetapi lolos sampai ACCEPT). Hasil di docs/eval/.
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.classifier.keras_model import KerasClassifier  # noqa: E402
from backend.config import load_classes, load_config  # noqa: E402
from backend.decision import decide  # noqa: E402
from backend.seed import load_seed_files  # noqa: E402

OUT_DIR = ROOT / "docs" / "eval"
SHOULD_REJECT = ("non_drug", "aerosol_inhaler", "out_of_dataset")


def main():
    cfg, classes = load_config(), load_classes()
    labels = [c["class_id"] for c in classes]
    products = {p["product_id"]: p for p in load_seed_files()[0]}
    product_of = {c["class_id"]: products[c["product_id"]] for c in classes if c["kind"] == "product"}
    clf = KerasClassifier()

    rows = []
    for path in sorted((ROOT / "dataset" / "test").glob("*/*")):
        if path.suffix.lower() in (".jpg", ".jpeg", ".png"):
            pred = clf.predict(path.read_bytes())
            rows.append({"file": f"{path.parent.name}/{path.name}", "true": path.parent.name,
                         "pred": pred["class_id"], "conf": pred["confidence"], "_pred": pred})

    # --- klasifikasi (out_of_dataset tidak punya kelas, jadi tidak ikut dihitung di sini) ---
    known = [r for r in rows if r["true"] in labels]
    accuracy = float(np.mean([r["true"] == r["pred"] for r in known]))
    matrix = np.zeros((len(labels), len(labels)), int)
    for r in known:
        matrix[labels.index(r["true"]), labels.index(r["pred"])] += 1
    per_class = {}
    for i, label in enumerate(labels):
        predicted, actual = matrix[:, i].sum(), matrix[i, :].sum()
        per_class[label] = {
            "precision": round(matrix[i, i] / predicted, 2) if predicted else None,
            "recall": round(matrix[i, i] / actual, 2) if actual else None,
            "n_test": int(actual),
        }

    # --- end-to-end lewat engine keputusan ---
    # Skenario terburuk: berat dianggap cocok dengan produk yang ditebak foto.
    def run(r, with_barcode):
        product = product_of.get(r["pred"])
        weight = (product["tare_g"] + product["gross_g"]) / 2 if product else 50.0
        barcode = {"present": True, "decoded": product["barcode"], "symbology": "EAN_13"} \
            if with_barcode and product else {"present": False}
        return decide({"deposits_today": 0}, r["_pred"], barcode, weight, cfg, products, classes)["decision"]

    bad = [r for r in rows if r["true"] in SHOULD_REJECT]
    good = [r for r in rows if r["true"] in product_of]
    for r in bad:
        r["accept_photo_only"] = run(r, False) == "ACCEPT"
        r["accept_with_barcode"] = run(r, True) == "ACCEPT"
    for r in good:
        # Produk asli dengan barcode dan berat yang benar: seharusnya diterima.
        product = product_of[r["true"]]
        result = decide({"deposits_today": 0}, r["_pred"],
                        {"present": True, "decoded": product["barcode"], "symbology": "EAN_13"},
                        (product["tare_g"] + product["gross_g"]) / 2, cfg, products, classes)
        r["rejected"] = result["decision"] == "REJECT"

    metrics = {
        "n_test_photos": len(rows),
        "accuracy": round(accuracy, 3),
        "per_class": per_class,
        "false_accept_rate_photo_only": round(float(np.mean([r["accept_photo_only"] for r in bad])), 3),
        "false_accept_rate_with_matching_barcode": round(float(np.mean([r["accept_with_barcode"] for r in bad])), 3),
        "n_should_reject": len(bad),
        "false_reject_rate_products": round(float(np.mean([r["rejected"] for r in good])), 3),
        "n_products": len(good),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    plot_confusion(matrix, labels, OUT_DIR / "confusion_matrix.png")
    write_report(metrics, rows, OUT_DIR / "report.md")
    print(json.dumps({k: v for k, v in metrics.items() if k != "per_class"}, indent=2))


def plot_confusion(matrix, labels, path):
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.imshow(matrix, cmap="Greens")
    ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlabel("Prediksi")
    ax.set_ylabel("Sebenarnya")
    ax.set_title("Confusion matrix (split test)")
    for i in range(len(labels)):
        for j in range(len(labels)):
            if matrix[i, j]:
                ax.text(j, i, matrix[i, j], ha="center", va="center",
                        color="white" if matrix[i, j] > matrix.max() / 2 else "black")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def write_report(m, rows, path):
    lines = [
        "# Hasil evaluasi model",
        "",
        f"Split test: {m['n_test_photos']} foto. Dataset kecil, jadi angka ini kasar dan bersifat indikatif.",
        "",
        "| Metrik | Nilai |",
        "|---|---|",
        f"| Akurasi klasifikasi (7 kelas) | {m['accuracy']:.0%} |",
        f"| False Accept Rate, hanya foto | {m['false_accept_rate_photo_only']:.0%} dari {m['n_should_reject']} barang |",
        f"| False Accept Rate, dengan barcode yang cocok | {m['false_accept_rate_with_matching_barcode']:.0%} dari {m['n_should_reject']} barang |",
        f"| Produk asli yang ditolak (barcode dan berat benar) | {m['false_reject_rate_products']:.0%} dari {m['n_products']} foto |",
        "",
        "False Accept Rate dihitung untuk foto bukan obat, aerosol/inhaler, dan obat di luar dataset, dengan asumsi terburuk "
        "bahwa berat barang cocok dengan produk yang ditebak foto.",
        "",
        "## Per kelas",
        "",
        "| Kelas | Precision | Recall | Foto test |",
        "|---|---|---|---|",
    ]
    for label, v in m["per_class"].items():
        lines.append(f"| {label} | {v['precision'] if v['precision'] is not None else '-'} | "
                     f"{v['recall'] if v['recall'] is not None else '-'} | {v['n_test']} |")
    lines += ["", "## Semua prediksi", "", "| Foto | Sebenarnya | Prediksi | Keyakinan |", "|---|---|---|---|"]
    for r in rows:
        mark = "" if r["true"] == r["pred"] else " (salah)" if r["true"] != "out_of_dataset" else ""
        lines.append(f"| {r['file']} | {r['true']} | {r['pred']}{mark} | {r['conf']:.0%} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
