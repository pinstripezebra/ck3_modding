"""One-off generator for Elder Magic culture-tradition item icons (Replicate/Flux -> DDS)."""

import os
import pathlib
import sys
import time
from io import BytesIO

import httpx
from dotenv import load_dotenv
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tools.icons import _save_dds  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEST = (
    REPO_ROOT
    / "ElderMagic"
    / "gfx"
    / "interface"
    / "icons"
    / "culture_tradition"
    / "4-items"
)
# Matches the vanilla 4-items layer canvas.
WIDTH, HEIGHT = 545, 285
GEN_WIDTH, GEN_HEIGHT = 1088, 568

ICONS = {
    "sorcerous_heritage": (
        "flat vector emblem on a pure solid black background, single centered symbol, "
        "an open ancient grimoire with a glowing arcane rune circle rising above it, "
        "warm pale gold and bone-white line art, heraldic engraved woodcut style, "
        "high contrast, simple bold silhouette, "
        "absolutely no text, no letters, no words, no watermark, no logo, no border, no frame"
    ),
    "necrotic_reanimators": (
        "flat vector emblem on a pure solid black background, single centered symbol, "
        "a human skull crowned with a ring of bone and two crossed femurs below, "
        "pale sickly green and bone-white line art, heraldic engraved woodcut style, "
        "high contrast, simple bold silhouette, "
        "absolutely no text, no letters, no words, no watermark, no logo, no border, no frame"
    ),
}


def _generate(token: str, prompt: str) -> Image.Image:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions",
            headers=headers,
            json={
                "input": {
                    "prompt": prompt,
                    "width": GEN_WIDTH,
                    "height": GEN_HEIGHT,
                    "num_outputs": 1,
                    "output_format": "png",
                }
            },
        )
        resp.raise_for_status()
        prediction = resp.json()

        deadline = time.time() + 300
        while prediction["status"] not in ("succeeded", "failed", "canceled"):
            if time.time() > deadline:
                raise RuntimeError("timed out waiting for prediction")
            time.sleep(2)
            poll = client.get(prediction["urls"]["get"], headers=headers)
            if poll.status_code >= 500:  # transient API hiccup, keep polling
                continue
            poll.raise_for_status()
            prediction = poll.json()

        if prediction["status"] != "succeeded":
            raise RuntimeError(f"prediction {prediction['status']}: {prediction.get('error')}")

        output = prediction["output"]
        url = output[0] if isinstance(output, list) else output
        data = client.get(url, follow_redirects=True).content

    return Image.open(BytesIO(data)).convert("RGBA")


def _key_out_black(img: Image.Image, threshold: int = 40) -> Image.Image:
    """Turn the near-black generated backdrop transparent so the icon composits
    over the vanilla background/pattern layers."""
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = px[x, y]
            luma = max(r, g, b)
            if luma <= threshold:
                px[x, y] = (r, g, b, 0)
            elif luma < threshold * 3:
                px[x, y] = (r, g, b, int(a * (luma - threshold) / (threshold * 2)))
    return img


def main() -> None:
    load_dotenv(REPO_ROOT / ".env")
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise SystemExit("REPLICATE_API_TOKEN is not set")

    DEST.mkdir(parents=True, exist_ok=True)
    for name, prompt in ICONS.items():
        img = _generate(token, prompt).resize((WIDTH, HEIGHT), Image.LANCZOS)
        img = _key_out_black(img)
        path = DEST / f"{name}.dds"
        _save_dds(img, path)
        print(f"wrote {path}", flush=True)


if __name__ == "__main__":
    main()
