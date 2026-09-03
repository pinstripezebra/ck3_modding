"""One-off generator for Elder Magic men-at-arms illustrations (Replicate/Flux -> DDS)."""

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
DEST = REPO_ROOT / "ElderMagic" / "gfx" / "interface" / "illustrations" / "men_at_arms_big"
WIDTH, HEIGHT = 680, 400
GEN_WIDTH, GEN_HEIGHT = 1360, 800

UNITS = {
    "skeleton_warriors": (
        "painterly medieval fantasy oil painting, muted desaturated palette, "
        "a disciplined rank of animated skeleton soldiers in rusted mail carrying spears and battered "
        "shields, hollow eye sockets glowing faint green, marching across a grey battlefield under an "
        "overcast sky, historical grand strategy concept art, plain uncluttered composition, "
        "absolutely no text, no letters, no words, no watermark, no logo, no signature, no border"
    ),
    "corpse_colossus": (
        "painterly medieval fantasy oil painting, muted desaturated palette, "
        "a towering hulking giant stitched together from many corpses, bound with iron chains and "
        "necromantic sigils, looming over tiny robed necromancers on a ruined battlefield, ominous "
        "sickly green light, historical grand strategy concept art, plain uncluttered composition, "
        "absolutely no text, no letters, no words, no watermark, no logo, no signature, no border"
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


def main() -> None:
    load_dotenv(REPO_ROOT / ".env")
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise SystemExit("REPLICATE_API_TOKEN is not set")

    DEST.mkdir(parents=True, exist_ok=True)
    for name, prompt in UNITS.items():
        img = _generate(token, prompt).resize((WIDTH, HEIGHT), Image.LANCZOS)
        path = DEST / f"{name}.dds"
        _save_dds(img, path)
        print(f"wrote {path}", flush=True)


if __name__ == "__main__":
    main()
