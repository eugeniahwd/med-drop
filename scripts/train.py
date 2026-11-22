"""Latih classifier foto: MobileNetV2 (bobot ImageNet) + lapisan klasifikasi baru.

    python scripts/train.py               # base dibekukan, hanya lapisan baru yang dilatih
    python scripts/train.py --fine-tune   # lalu latih juga 20 lapisan terakhir base

Hasil: model/model.keras dan model/labels.json
"""

import argparse
import json
import sys
from pathlib import Path

import tensorflow as tf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import load_classes  # noqa: E402

IMAGE_SIZE = (224, 224)
SEED = 42


def load_split(split, labels):
    return tf.keras.utils.image_dataset_from_directory(
        ROOT / "dataset" / split, label_mode="categorical", class_names=labels,
        image_size=IMAGE_SIZE, batch_size=8, shuffle=(split == "train"), seed=SEED)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--fine-tune", action="store_true")
    args = parser.parse_args()

    tf.keras.utils.set_random_seed(SEED)
    labels = [c["class_id"] for c in load_classes()]
    train, val = load_split("train", labels), load_split("val", labels)

    # Augmentasi ringan karena fotonya sedikit (sekitar 6 per kelas untuk latihan).
    augment = tf.keras.Sequential([
        tf.keras.layers.RandomRotation(0.05),
        tf.keras.layers.RandomZoom(0.15),
        tf.keras.layers.RandomTranslation(0.1, 0.1),
        tf.keras.layers.RandomBrightness(0.2),
        tf.keras.layers.RandomContrast(0.2),
    ])
    base = tf.keras.applications.MobileNetV2(input_shape=IMAGE_SIZE + (3,), include_top=False,
                                             weights="imagenet", pooling="avg")
    base.trainable = False

    inputs = tf.keras.Input(shape=IMAGE_SIZE + (3,))
    x = augment(inputs)
    x = tf.keras.layers.Rescaling(1 / 127.5, offset=-1)(x)  # sama dengan preprocess_input MobileNetV2
    x = base(x, training=False)
    x = tf.keras.layers.Dropout(0.3)(x)
    outputs = tf.keras.layers.Dense(len(labels), activation="softmax")(x)
    model = tf.keras.Model(inputs, outputs)

    stop = tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=6, restore_best_weights=True)
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="categorical_crossentropy", metrics=["accuracy"])
    model.fit(train, validation_data=val, epochs=args.epochs, callbacks=[stop])

    if args.fine_tune:
        base.trainable = True
        for layer in base.layers[:-20]:
            layer.trainable = False
        model.compile(optimizer=tf.keras.optimizers.Adam(1e-5), loss="categorical_crossentropy", metrics=["accuracy"])
        model.fit(train, validation_data=val, epochs=10, callbacks=[stop])

    out = ROOT / "model"
    out.mkdir(exist_ok=True)
    model.save(out / "model.keras")
    (out / "labels.json").write_text(json.dumps(labels, indent=2), encoding="utf-8")
    print(f"Model disimpan di {out}")


if __name__ == "__main__":
    main()
