"""
Sprint 1 / D1: render an architecture diagram for Istio's Bookinfo sample app,
since the repo (istio/istio) doesn't ship one in-tree for this sample.

Unlike the other 9 diagrams in this dataset, this image is drawn by us rather
than downloaded - but every box and arrow below is derived from reading the
real Bookinfo service source code, not guessed or fabricated:

- productpage -> details:
    samples/bookinfo/src/productpage/productpage.py:53-54,62-64,267
    (detailsHostname/detailsPort config, `details` service dict, getProductDetails())
- productpage -> reviews:
    samples/bookinfo/src/productpage/productpage.py:57-58,74-76,272
    (reviewsHostname/reviewsPort config, `reviews` service dict, getProductReviews())
- reviews -> ratings:
    samples/bookinfo/src/reviews/reviews-application/src/main/java/application/rest/LibertyRestEndpoint.java:42-44,151,191
    (ratings_hostname/ratings_service URL, getRatings(), called from the review-fetching path)

Repo: https://github.com/istio/istio (Apache-2.0)
Commit read: 399ef1bff5261a01708c13b73a93cdc20189b08a
"""

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_PATH = Path(__file__).resolve().parents[2] / "data" / "diagrams" / "raw" / "istio_bookinfo_derived.png"
SOURCES_PATH = OUT_PATH.parent / "SOURCES.md"

SOURCES_ENTRY = """
## istio_bookinfo_derived.png
- diagram_id: `istio_bookinfo_derived`
- source: rendered by us (`backend/scripts/derive_bookinfo_diagram.py`) - no in-repo diagram exists for this sample
- repository: https://github.com/istio/istio (samples/bookinfo)
- commit: `399ef1bff5261a01708c13b73a93cdc20189b08a`
- license: Apache-2.0
- description: Bookinfo sample app. Diagram provenance is "derived", not "official" - every box/arrow is backed by real evidence citations (file + line) recorded in `data/annotations/manifest.json`, read directly from the real service source code.
"""

WIDTH, HEIGHT = 900, 500

BOXES = {
    "productpage": (370, 40, 530, 110),
    "details": (120, 220, 280, 290),
    "reviews": (620, 220, 780, 290),
    "ratings": (620, 380, 780, 450),
}

EDGES = [
    ("productpage", "details"),
    ("productpage", "reviews"),
    ("reviews", "ratings"),
]


def _box_center(box):
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2, (y1 + y2) / 2


def render():
    img = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()

    for src, dst in EDGES:
        x1, y1 = _box_center(BOXES[src])
        x2, y2 = _box_center(BOXES[dst])
        draw.line((x1, y1, x2, y2), fill="black", width=2)
        # simple arrowhead
        angle = math.atan2(y2 - y1, x2 - x1)
        ah = 10
        for a in (angle + 2.7, angle - 2.7):
            draw.line((x2, y2, x2 - ah * math.cos(a), y2 - ah * math.sin(a)), fill="black", width=2)

    for name, (x1, y1, x2, y2) in BOXES.items():
        draw.rectangle((x1, y1, x2, y2), outline="black", fill="#aec7e8", width=2)
        tw = draw.textlength(name, font=font)
        draw.text((((x1 + x2) / 2) - tw / 2, (y1 + y2) / 2 - 10), name, fill="black", font=font)

    draw.text((20, HEIGHT - 30), "Derived from istio/istio samples/bookinfo source (Apache-2.0)", fill="gray", font=font)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT_PATH)
    print(f"wrote {OUT_PATH}")


def append_sources_entry():
    """Append this diagram's provenance to SOURCES.md, idempotently."""
    existing = SOURCES_PATH.read_text(encoding="utf-8") if SOURCES_PATH.exists() else "# SOURCES.md\n"
    if "istio_bookinfo_derived.png" in existing:
        return
    SOURCES_PATH.write_text(existing.rstrip("\n") + "\n" + SOURCES_ENTRY, encoding="utf-8")
    print(f"appended istio_bookinfo_derived entry to {SOURCES_PATH}")


if __name__ == "__main__":
    render()
    append_sources_entry()
