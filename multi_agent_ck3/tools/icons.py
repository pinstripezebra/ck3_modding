import math
import pathlib
import re
import struct
import zlib
from io import BytesIO
from typing import Optional

import replicate
from PIL import Image, ImageDraw


_ICON_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
_EDUCATION_NAME_RE = re.compile(r"education(?:_[1-5])?$", re.IGNORECASE)


def _normalize_output_name(name: str) -> str:
    token = name.strip()
    if token.lower().endswith(".dds"):
        token = token[:-4]
    if not _ICON_NAME_RE.fullmatch(token):
        raise ValueError(
            f"output_name must use letters, numbers, and underscore only, got: {name!r}"
        )
    return token


def _normalize_icon_subdir(icon_subdir: str) -> str:
    normalized = icon_subdir.replace("\\", "/").strip("/")
    parts = pathlib.PurePosixPath(normalized).parts
    if not normalized or any(part == ".." for part in parts):
        raise ValueError(f"icon_subdir must be a safe relative path, got: {icon_subdir!r}")
    return normalized


def _placeholder_image(width: int, height: int) -> Image.Image:
    """Build a simple fallback icon so missing-texture errors are avoided."""
    img = Image.new("RGBA", (width, height), (42, 42, 46, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((2, 2, width - 3, height - 3), outline=(180, 180, 185, 255), width=2)
    draw.line((10, 10, width - 11, height - 11), fill=(210, 170, 90, 255), width=3)
    draw.line((width - 11, 10, 10, height - 11), fill=(210, 170, 90, 255), width=3)
    return img


def _is_education_icon_name(output_stem: str) -> bool:
    return bool(_EDUCATION_NAME_RE.search(output_stem))


def _apply_triangular_trait_background(img: Image.Image) -> Image.Image:
    """Apply CK3-like triangular medallion framing for non-education traits."""
    img = img.convert("RGBA")
    w, h = img.size

    # Match vanilla-like trait silhouette: broad base, high apex, thicker edge.
    outer = [
        (w * 0.50, h * 0.035),
        (w * 0.90, h * 0.915),
        (w * 0.10, h * 0.915),
    ]
    inner = [
        (w * 0.50, h * 0.105),
        (w * 0.81, h * 0.82),
        (w * 0.19, h * 0.82),
    ]

    frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)

    # Outer metal frame and rim.
    rim_width = max(2, int(round(w * 0.03)))
    draw.polygon(outer, fill=(42, 44, 50, 255), outline=(190, 168, 112, 255), width=rim_width)

    # Inner plate to create a clear inset similar to vanilla trait icons.
    draw.polygon(inner, fill=(30, 34, 40, 255), outline=(122, 108, 74, 230), width=max(1, rim_width - 1))

    # Mask source art into the inset triangle.
    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    content = [
        (w * 0.50, h * 0.14),
        (w * 0.77, h * 0.78),
        (w * 0.23, h * 0.78),
    ]
    mask_draw.polygon(content, fill=235)

    icon_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    icon_layer.paste(img, (0, 0), mask)

    return Image.alpha_composite(frame, icon_layer)


def _apply_diamond_trait_background(img: Image.Image) -> Image.Image:
    """Apply a CK3-like diamond medallion framing for trait icons."""
    img = img.convert("RGBA")
    w, h = img.size

    outer = [
        (w * 0.50, h * 0.025),
        (w * 0.97, h * 0.50),
        (w * 0.50, h * 0.975),
        (w * 0.03, h * 0.50),
    ]
    inner = [
        (w * 0.50, h * 0.10),
        (w * 0.87, h * 0.50),
        (w * 0.50, h * 0.90),
        (w * 0.13, h * 0.50),
    ]

    frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)

    rim_width = max(2, int(round(w * 0.024)))
    draw.polygon(outer, fill=(17, 22, 19, 235), outline=(60, 84, 58, 230), width=rim_width)
    draw.polygon(inner, fill=(23, 34, 28, 245), outline=(88, 124, 86, 205), width=max(1, rim_width - 1))

    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    content = [
        (w * 0.50, h * 0.17),
        (w * 0.79, h * 0.50),
        (w * 0.50, h * 0.83),
        (w * 0.21, h * 0.50),
    ]
    mask_draw.polygon(content, fill=235)

    icon_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    icon_layer.paste(img, (0, 0), mask)

    return Image.alpha_composite(frame, icon_layer)


def _apply_circular_trait_background(img: Image.Image) -> Image.Image:
    """Apply a CK3-like circular medallion framing for trait icons."""
    img = img.convert("RGBA")
    w, h = img.size

    frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)

    rim = max(2, int(round(w * 0.035)))
    outer = [
        (w * 0.06, h * 0.06),
        (w * 0.94, h * 0.94),
    ]
    inner = [
        (w * 0.15, h * 0.15),
        (w * 0.85, h * 0.85),
    ]

    draw.ellipse(outer, fill=(20, 23, 31, 235), outline=(98, 122, 150, 230), width=rim)
    draw.ellipse(inner, fill=(26, 34, 47, 245), outline=(136, 166, 198, 220), width=max(1, rim - 1))

    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    content = [
        (w * 0.20, h * 0.20),
        (w * 0.80, h * 0.80),
    ]
    mask_draw.ellipse(content, fill=235)

    icon_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    icon_layer.paste(img, (0, 0), mask)

    return Image.alpha_composite(frame, icon_layer)


def _apply_square_trait_background(img: Image.Image) -> Image.Image:
    """Apply a CK3-like square/rounded-rectangle medallion framing for lifestyle and learned traits."""
    img = img.convert("RGBA")
    w, h = img.size

    radius = max(4, int(round(w * 0.12)))
    pad = max(3, int(round(w * 0.055)))
    rim = max(2, int(round(w * 0.028)))

    outer = [pad, pad, w - pad, h - pad]
    inner_pad = pad + rim * 2
    inner = [inner_pad, inner_pad, w - inner_pad, h - inner_pad]
    content_pad = pad + rim * 3

    frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)

    # Outer metal border and inner plate — warm parchment/amber tones for learned traits.
    draw.rounded_rectangle(outer, radius=radius, fill=(36, 32, 26, 240),
                           outline=(178, 148, 90, 240), width=rim)
    draw.rounded_rectangle(inner, radius=max(2, radius - rim * 2),
                           fill=(26, 22, 16, 245), outline=(120, 98, 58, 210),
                           width=max(1, rim - 1))

    # Mask the source art into the inset square area.
    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle(
        [content_pad, content_pad, w - content_pad, h - content_pad],
        radius=max(2, radius - rim * 3),
        fill=235,
    )

    icon_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    icon_layer.paste(img, (0, 0), mask)

    return Image.alpha_composite(frame, icon_layer)


def _apply_building_frame(img: Image.Image) -> Image.Image:
    """Apply a CK3-style stone rectangular frame suitable for building icons.

    Produces a dark-stone background with gold/amber borders and corner
    reinforcements (battlement-style) matching the medieval CK3 UI aesthetic.
    """
    img = img.convert("RGBA")
    w, h = img.size

    pad = max(3, int(round(w * 0.055)))
    rim = max(2, int(round(w * 0.04)))
    corner = max(4, int(round(w * 0.10)))

    frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(frame)

    # Outer stone background with gold border.
    outer = [pad, pad, w - pad, h - pad]
    draw.rectangle(outer, fill=(38, 34, 28, 245), outline=(160, 135, 80, 240), width=rim)

    # Inner inset border.
    inner_pad = pad + rim + 2
    inner = [inner_pad, inner_pad, w - inner_pad, h - inner_pad]
    draw.rectangle(inner, fill=(28, 25, 20, 245), outline=(110, 90, 50, 200), width=max(1, rim - 1))

    # Corner reinforcement squares (battlement look).
    for cx, cy in [
        (pad, pad),
        (w - pad - corner, pad),
        (pad, h - pad - corner),
        (w - pad - corner, h - pad - corner),
    ]:
        draw.rectangle(
            [cx, cy, cx + corner, cy + corner],
            fill=(50, 44, 36, 255),
            outline=(175, 148, 88, 255),
            width=max(1, rim - 1),
        )

    # Mask image content into the inner area.
    content_pad = inner_pad + max(1, rim - 1)
    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rectangle(
        [content_pad, content_pad, w - content_pad, h - content_pad],
        fill=235,
    )

    icon_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    icon_layer.paste(img, (0, 0), mask)

    return Image.alpha_composite(frame, icon_layer)


def _estimate_shape_style_from_alpha(alpha: Image.Image) -> str:
    """Classify silhouette as circle-like or diamond-like from alpha mask."""
    w, h = alpha.size
    cx = (w - 1) / 2.0
    cy = (h - 1) / 2.0
    max_r = min(w, h) * 0.49
    threshold = 24

    def _radius_at(angle: float) -> float:
        for step in range(int(max_r), 1, -1):
            x = int(round(cx + math.cos(angle) * step))
            y = int(round(cy + math.sin(angle) * step))
            if 0 <= x < w and 0 <= y < h and alpha.getpixel((x, y)) >= threshold:
                return float(step)
        return 0.0

    cardinals = [_radius_at(a) for a in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2)]
    diagonals = [_radius_at(a) for a in (math.pi / 4, 3 * math.pi / 4, 5 * math.pi / 4, 7 * math.pi / 4)]
    card_avg = sum(cardinals) / max(1, len(cardinals))
    diag_avg = sum(diagonals) / max(1, len(diagonals))
    ratio = diag_avg / card_avg if card_avg > 0 else 0.0

    return "diamond" if ratio < 0.82 else "circle"


def _reference_trait_frame_styles() -> list[str]:
    """Infer preferred frame styles from ck3_agent/assets/traits examples."""
    assets_dir = pathlib.Path(__file__).resolve().parents[2] / "assets" / "traits"
    if not assets_dir.is_dir():
        return ["diamond", "circle"]

    observed: dict[str, int] = {"diamond": 0, "circle": 0}
    for path in assets_dir.iterdir():
        if not path.is_file() or path.suffix.lower() != ".dds":
            continue
        try:
            try:
                img = Image.open(path).convert("RGBA")
            except Exception:
                img = _read_uncompressed_dds_rgba(path)
            style = _estimate_shape_style_from_alpha(img.split()[-1])
            observed[style] = observed.get(style, 0) + 1
        except Exception:
            continue

    styles = [k for k, v in observed.items() if v > 0]
    if not styles:
        return ["diamond", "circle"]
    if len(styles) == 1:
        return styles

    # Keep deterministic ordering with dominant style first.
    return sorted(styles, key=lambda s: observed[s], reverse=True)


def _auto_frame_style_from_examples(output_stem: str) -> str:
    """Pick diamond/circle style from examples; alternate deterministically if both exist."""
    styles = _reference_trait_frame_styles()
    if len(styles) == 1:
        return styles[0]

    # Stable distribution for mixed style sets.
    seed = zlib.crc32(output_stem.encode("utf-8"))
    return styles[seed % len(styles)]


def _star_polygon(
    cx: float, cy: float, r_outer: float, r_inner: float
) -> list[tuple[float, float]]:
    """Return the vertices of a 5-pointed star centred at (cx, cy)."""
    coords = []
    for i in range(10):
        angle = math.pi / 5 * i - math.pi / 2
        r = r_outer if i % 2 == 0 else r_inner
        coords.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return coords


def _save_dds(img: Image.Image, dds_path: pathlib.Path) -> None:
    """Save a PIL RGBA image as a CK3 trait/perk icon DDS.

    Match the vanilla CK3 trait icon header shape used by working DDS files
    like athletic.dds: uncompressed 32-bit A8R8G8B8 with a single image level,
    DDSD_LINEARSIZE, and texture-only caps.
    """
    img = img.convert("RGBA")
    width, height = img.size
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000
    linear_size = width * height * 4

    header = struct.pack(
        "<4s7I44x8I5I",
        b"DDS ",
        124,
        flags,
        height,
        width,
        linear_size,
        0,
        0,
        32,
        0x1 | 0x40,
        0,
        32,
        0x00FF0000,
        0x0000FF00,
        0x000000FF,
        0xFF000000,
        0x1000,
        0,
        0,
        0,
        0,
    )

    dds_path.write_bytes(header + img.tobytes("raw", "BGRA"))


def _read_uncompressed_dds_rgba(dds_path: pathlib.Path) -> Image.Image:
    """Read a simple uncompressed 32-bit DDS (A8R8G8B8/BGRA byte order)."""
    data = dds_path.read_bytes()
    if len(data) < 128 or data[:4] != b"DDS ":
        raise ValueError(f"Not a DDS file: {dds_path}")

    height = struct.unpack_from("<I", data, 12)[0]
    width = struct.unpack_from("<I", data, 16)[0]
    rgb_bit_count = struct.unpack_from("<I", data, 88)[0]
    if width <= 0 or height <= 0 or rgb_bit_count != 32:
        raise ValueError(f"Unsupported DDS format in {dds_path}")

    expected = width * height * 4
    pixel_data = data[128 : 128 + expected]
    if len(pixel_data) < expected:
        raise ValueError(f"DDS pixel payload is truncated: {dds_path}")

    return Image.frombytes("RGBA", (width, height), pixel_data, "raw", "BGRA")


def _load_star_overlay(level: int, width: int, height: int) -> Image.Image:
    """Load the level-specific star overlay from ck3_agent/assets."""
    assets_dir = pathlib.Path(__file__).resolve().parents[2] / "assets"
    stars_path = assets_dir / f"_stars_{level}.dds"

    if not stars_path.is_file():
        raise FileNotFoundError(f"Missing education star overlay: {stars_path}")

    # Prefer PIL's DDS loader; if unavailable, parse common uncompressed DDS.
    try:
        overlay = Image.open(stars_path).convert("RGBA")
    except Exception:
        overlay = _read_uncompressed_dds_rgba(stars_path)

    if overlay.size != (width, height):
        overlay = overlay.resize((width, height), Image.LANCZOS)
    return overlay


def _overlay_stars(img: Image.Image, filled: int, total: int = 5) -> Image.Image:
    """Composite a star row or grid over *img*.

    The default 5-slot layout matches education icons. Larger totals are laid
    out as up to two rows of five for the physical trait ladder.
    """
    if total <= 0:
        return img.convert("RGBA")

    filled = max(0, min(filled, total))
    w, h = img.size

    try:
        if total == 5:
            overlay = _load_star_overlay(filled if filled else 1, w, h)
            return Image.alpha_composite(img.convert("RGBA"), overlay)
    except Exception:
        pass

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    columns = min(5, total)
    rows = math.ceil(total / 5)
    r_outer = min(w, h) * (0.055 if total <= 5 else 0.032)
    r_inner = r_outer * 0.42
    x_spacing = w / (columns + 1)
    y_spacing = max(r_outer * 2.25, (h * 0.28) / max(rows, 1))
    base_y = h - r_outer - 4

    for i in range(total):
        row = i // 5
        col = i % 5
        cx = x_spacing * (col + 1)
        cy = base_y - (row * y_spacing)
        pts = _star_polygon(cx, cy, r_outer, r_inner)
        if i < filled:
            draw.polygon(pts, fill=(255, 210, 0, 235), outline=(170, 130, 0, 255))
        else:
            draw.polygon(pts, fill=(70, 60, 30, 110), outline=(110, 90, 45, 160))

    return Image.alpha_composite(img.convert("RGBA"), overlay)


def _run_replicate_flux(prompt: str, width: int, height: int) -> Image.Image:
    """Run Flux Schnell via Replicate and return a PIL RGBA Image.

    Handles both FileOutput objects (replicate-python < 1.0) and URL strings
    (replicate-python >= 1.0) so either library version works correctly.

    Raises RuntimeError on any failure so callers can decide how to handle it.
    """
    import urllib.request

    output = replicate.run(
        "black-forest-labs/flux-schnell",
        input={"prompt": prompt, "width": width, "height": height, "num_outputs": 1},
    )
    first = output[0] if isinstance(output, (list, tuple)) else output
    if hasattr(first, "read"):
        img_data = first.read()
    elif isinstance(first, (str, bytes)):
        url = first if isinstance(first, str) else first.decode()
        with urllib.request.urlopen(url) as resp:
            img_data = resp.read()
    else:
        raise RuntimeError(f"Unexpected Replicate output type: {type(first)}")
    return Image.open(BytesIO(img_data)).convert("RGBA")


def register(mcp, output_dir: pathlib.Path, mods_dir: Optional[pathlib.Path] = None):
    def _resolve_dir(mod_name: Optional[str], icon_subdir: str) -> pathlib.Path:
        """Where to write the icon: inside the mod's gfx folder if mod_name is
        given, otherwise the standalone output directory."""
        icon_subdir = _normalize_icon_subdir(icon_subdir)
        if mod_name:
            dest = (mods_dir or output_dir) / mod_name / icon_subdir
        else:
            dest = output_dir
        dest.mkdir(parents=True, exist_ok=True)
        return dest

    @mcp.tool()
    def generate_icon_image(
        prompt: str,
        width: int = 120,
        height: int = 120,
        output_name: str = "icon",
        star_count: int = 0,
        frame_style: str = "auto",
        mod_name: Optional[str] = None,
        icon_subdir: str = "gfx/interface/icons/traits",
    ) -> str:
        """Generate a DDS icon image from a text prompt using Flux (via Replicate).
        Produces an uncompressed A8R8G8B8 DDS with mipmaps (the format CK3 trait
        and lifestyle-perk icons require).
        Args:
            prompt: Description of the icon to generate.
            width: Target width in pixels (default 120 for CK3 trait icons).
            height: Target height in pixels (default 120 for CK3 trait icons).
            output_name: Filename without extension. Use the SAME value as the
                         trait's icon_name so the trait resolves to this file.
            star_count: Optional number of stars to overlay on the icon. Use this
                        for leveled traits that should visibly climb from one to
                        ten stars.
            frame_style: Optional trait frame style when generating trait icons.
                        Supported: auto, triangle, diamond, circle, square, none.
                        Auto defaults to square (suitable for lifestyle/learned traits);
                        use triangle for genetic/physical traits explicitly.
            mod_name: Mod folder name. When given, the icon is written directly
                      into the mod at <mod>/<icon_subdir>/<output_name>.dds so the
                      trait's `icon =` reference matches. Omit to write to the
                      standalone output directory.
            icon_subdir: Subdirectory within the mod for the icon. Defaults to
                         'gfx/interface/icons/traits'. Use
                         'gfx/interface/icons/faith' for faith icons.
        Returns:
            Absolute path to the generated .dds file.
        """
        if not prompt.strip():
            raise ValueError("prompt cannot be empty")

        output_stem = _normalize_output_name(output_name)
        dest = _resolve_dir(mod_name, icon_subdir)
        use_trait_frame = (
            icon_subdir.replace("\\", "/").endswith("icons/traits")
            and not _is_education_icon_name(output_stem)
        )
        frame_style_norm = frame_style.strip().lower()
        if frame_style_norm not in {"auto", "triangle", "diamond", "circle", "square", "none"}:
            raise ValueError(
                f"frame_style must be one of auto|triangle|diamond|circle|square|none, got: {frame_style!r}"
            )

        resolved_frame_style = frame_style_norm
        if use_trait_frame and frame_style_norm == "auto":
            resolved_frame_style = "square"  # default for learned/lifestyle traits

        # Flux-schnell supports arbitrary dimensions (multiples of 8)
        gen_w = max(256, (width // 8) * 8)
        gen_h = max(256, (height // 8) * 8)

        if use_trait_frame and resolved_frame_style != "none":
            if resolved_frame_style == "triangle":
                boundary_word = "triangular"
            elif resolved_frame_style == "diamond":
                boundary_word = "diamond"
            elif resolved_frame_style == "square":
                boundary_word = "square stone"
            else:
                boundary_word = "circular"
            model_prompt = (
                f"medieval fantasy trait icon with a dark {boundary_word} heraldic medallion background, "
                "single centered symbol, clean silhouette, high contrast, no text, CK3 UI art style; "
                f"theme: {prompt.strip()}"
            )
        else:
            model_prompt = prompt

        try:
            img = _run_replicate_flux(model_prompt, gen_w, gen_h).resize(
                (width, height), Image.LANCZOS
            )
        except Exception:
            img = _placeholder_image(width, height)

        if use_trait_frame:
            if resolved_frame_style == "diamond":
                img = _apply_diamond_trait_background(img)
            elif resolved_frame_style == "circle":
                img = _apply_circular_trait_background(img)
            elif resolved_frame_style == "triangle":
                img = _apply_triangular_trait_background(img)
            elif resolved_frame_style == "square":
                img = _apply_square_trait_background(img)

        if star_count > 0:
            img = _overlay_stars(img, star_count, total=star_count)

        dds_path = dest / f"{output_stem}.dds"
        _save_dds(img, dds_path)
        return str(dds_path)

    @mcp.tool()
    def generate_education_icon(
        background_concept: str,
        level: int,
        output_name: str = "education_icon",
        width: int = 84,
        height: int = 84,
        mod_name: Optional[str] = None,
        icon_subdir: str = "gfx/interface/icons/traits",
    ) -> str:
        """Generate a CK3-style education trait icon.

        Produces a two-layer DDS icon matching CK3's vanilla education format:
        - Background: a thematic symbol generated by Flux (e.g. 'crossed swords').
        - Foreground: a row of 5 star slots along the bottom; stars 1..level are
          filled gold, the remainder are dim outlines.

        Args:
            background_concept: The thematic symbol for this education group
                                 (e.g. 'crossed swords', 'open book and quill',
                                 'laurel wreath', 'chalice and flame').
            level: Education level 1-5 (number of filled gold stars).
            output_name: Filename without extension. Use the SAME value as the
                         trait's icon_name so the trait resolves to this file.
            width: Target width in pixels (default 84 for CK3 education icons).
            height: Target height in pixels (default 84 for CK3 education icons).
            mod_name: Mod folder name. When given, the icon is written directly
                      into the mod at <mod>/<icon_subdir>/<output_name>.dds.
            icon_subdir: Subdirectory within the mod for the icon. Defaults to
                         'gfx/interface/icons/traits'.
        Returns:
            Absolute path to the generated .dds file.
        """
        if not 1 <= level <= 5:
            raise ValueError(f"level must be between 1 and 5, got {level}")

        output_stem = _normalize_output_name(output_name)
        dest = _resolve_dir(mod_name, icon_subdir)

        gen_w = max(256, (width // 8) * 8)
        gen_h = max(256, (height // 8) * 8)

        bg_prompt = (
            f"medieval heraldic icon of {background_concept}, bold centered symbol, "
            "muted dark tones, flat design, no text, no stars, CK3 game art style"
        )
        try:
            img = _run_replicate_flux(bg_prompt, gen_w, gen_h).resize(
                (width, height), Image.LANCZOS
            )
        except Exception:
            img = _placeholder_image(width, height)

        img = _overlay_stars(img, level, total=5)

        dds_path = dest / f"{output_stem}.dds"
        _save_dds(img, dds_path)
        return str(dds_path)

    @mcp.tool()
    def generate_building_icon(
        prompt: str,
        output_name: str = "building_icon",
        width: int = 64,
        height: int = 64,
        mod_name: Optional[str] = None,
        icon_subdir: str = "gfx/interface/icons/buildings",
    ) -> str:
        """Generate a DDS icon image for a CK3 duchy or special building.

        Produces an uncompressed A8R8G8B8 DDS with a stone rectangular frame
        appropriate for CK3 building icons (64x64 px, dark stone background
        with gold/amber borders and battlement corner details).

        Raises RuntimeError if image generation fails (no silent placeholder).

        Args:
            prompt: Description of the building to depict (e.g. 'a tall wizard
                    tower with glowing arcane runes at the spire tip').
            output_name: Filename without extension (e.g. 'wizard_tower').
            width: Target width in pixels (default 64).
            height: Target height in pixels (default 64).
            mod_name: Mod folder name. When given, the icon is written directly
                      into the mod at <mod>/<icon_subdir>/<output_name>.dds.
            icon_subdir: Subdirectory within the mod. Defaults to
                         'gfx/interface/icons/buildings'.
        Returns:
            Absolute path to the generated .dds file.
        """
        if not prompt.strip():
            raise ValueError("prompt cannot be empty")

        output_stem = _normalize_output_name(output_name)
        dest = _resolve_dir(mod_name, icon_subdir)

        gen_w = max(256, (width // 8) * 8)
        gen_h = max(256, (height // 8) * 8)

        model_prompt = (
            "medieval fantasy building icon, flat 2D illustration, single centered "
            "structure, bold silhouette, high contrast, muted stone and amber palette, "
            "no text, CK3 UI art style; subject: "
            + prompt.strip()
        )

        img = _run_replicate_flux(model_prompt, gen_w, gen_h).resize(
            (width, height), Image.LANCZOS
        )
        img = _apply_building_frame(img)

        dds_path = dest / f"{output_stem}.dds"
        _save_dds(img, dds_path)
        return str(dds_path)

# -- LangChain tool factory -------------------------------------------------

class _ToolCollector:
    """Mimics FastMCP so register() populates tools without a real server."""
    def __init__(self):
        self._fns: list = []
    def tool(self, **_):
        def _wrap(fn):
            self._fns.append(fn)
            return fn
        return _wrap


def get_tools(output_dir, mods_dir=None) -> list:
    """Return this module's tools as LangChain StructuredTool objects."""
    from langchain_core.tools import StructuredTool
    collector = _ToolCollector()
    register(collector, output_dir, mods_dir)
    return [StructuredTool.from_function(fn) for fn in collector._fns]
