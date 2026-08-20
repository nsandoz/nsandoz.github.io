#!/usr/bin/env python3
"""Regenerate the gallery grid in gallery.html from the files in images/gallery/.

This is what makes "drop a photo in the folder and push" work. Every photo in
images/gallery/ becomes one <div class="gallery-item"> tile, and the block
between the gallery:start / gallery:end markers in gallery.html is rewritten to
match. Nothing else in gallery.html is touched.

For each photo the script works out, without any third-party libraries:

  * real pixel dimensions, read straight from the JPEG/PNG header, so the
    width/height attributes reserve the right amount of layout space and the
    page does not jump around while photos load;
  * the EXIF orientation flag, so a photo the camera stored sideways is
    measured the way a browser will actually display it;
  * the number in the filename, used to sort highest first, so the newest
    photo leads the page (see sort_number below for exactly how it is read);
  * the closest tile shape from the item-* classes in css/style.css, chosen
    from the photo's true aspect ratio so photos are never cropped into a
    shape they were not shot in;
  * alt text derived from the filename.

Run it locally with:      python3 tools/build_gallery.py
Check without writing:    python3 tools/build_gallery.py --check
"""

import argparse
import os
import re
import struct
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GALLERY_DIR = os.path.join(REPO_ROOT, "images", "gallery")
GALLERY_HTML = os.path.join(REPO_ROOT, "gallery.html")
WEB_PREFIX = "images/gallery"

START_MARKER = "<!-- gallery:start -->"
END_MARKER = "<!-- gallery:end -->"

SUPPORTED = (".jpg", ".jpeg", ".png")

# Tile shapes available in css/style.css, as width/height ratios.
TILE_RATIOS = {
    "item-2x1": 2 / 1,
    "item-8x5": 8 / 5,
    "item-3x2": 3 / 2,
    "item-4x3": 4 / 3,
    "item-1x1": 1 / 1,
    "item-3x4": 3 / 4,
    "item-2x3": 2 / 3,
}

# Filenames that carry no human meaning, so no usable alt text can come from them.
UNDESCRIPTIVE = re.compile(r"^(image[-_ ]?\d+|img[-_ ]?\d+|dsc[-_ ]?\d+|[0-9a-z]{4}\d{3,}|photo[-_ ]?\d+)$", re.I)


# --------------------------------------------------------------------------
# Image headers
# --------------------------------------------------------------------------

def _png_size(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _jpeg_size(data):
    """Walk the JPEG marker segments looking for a start-of-frame header."""
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    end = len(data)
    while i < end - 1:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        # Padding and standalone markers carry no length field.
        if marker in (0xFF, 0x01) or 0xD0 <= marker <= 0xD9:
            i += 2
            continue
        if i + 4 > end:
            break
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        # Start-of-frame markers, excluding DHT (C4), JPG (C8) and DAC (CC).
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack(">HH", data[i + 5:i + 9])
            return width, height
        i += 2 + seg_len
    return None


def _exif_block(data):
    """Return the raw TIFF block from the JPEG's APP1 segment, if present."""
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    end = len(data)
    while i < end - 1:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xFF, 0x01) or 0xD0 <= marker <= 0xD9:
            i += 2
            continue
        if i + 4 > end:
            break
        seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
        payload = data[i + 4:i + 2 + seg_len]
        if marker == 0xE1 and payload[:6] == b"Exif\x00\x00":
            return payload[6:]
        if marker == 0xDA:  # start of scan: no metadata past here
            break
        i += 2 + seg_len
    return None


def _read_ifd(tiff, offset, endian, wanted):
    """Read one IFD, returning {tag: value} for the tags we care about."""
    out = {}
    if offset <= 0 or offset + 2 > len(tiff):
        return out
    count = struct.unpack(endian + "H", tiff[offset:offset + 2])[0]
    for n in range(count):
        entry = offset + 2 + n * 12
        if entry + 12 > len(tiff):
            break
        tag, typ, cnt, raw = struct.unpack(endian + "HHI4s", tiff[entry:entry + 12])
        if tag not in wanted:
            continue
        if typ == 3:  # SHORT
            out[tag] = struct.unpack(endian + "H", raw[:2])[0]
        elif typ == 4:  # LONG
            out[tag] = struct.unpack(endian + "I", raw)[0]
        elif typ == 2:  # ASCII
            value_off = struct.unpack(endian + "I", raw)[0]
            if cnt <= 4:
                text = raw[:cnt]
            else:
                text = tiff[value_off:value_off + cnt]
            out[tag] = text.split(b"\x00")[0].decode("ascii", "ignore")
    return out


def read_exif_orientation(data):
    """The EXIF orientation flag from a JPEG, best effort, defaulting to 1.

    Only the orientation is read. Ordering used to come from the EXIF capture
    date, but that turned out to be unreliable here: two thirds of the photos
    have a date and one third does not, and the fallback for the rest resolved
    to whichever commit last moved the file, so a routine rebuild could reshuffle
    the page. Filenames now decide the order; see sort_number.
    """
    tiff = _exif_block(data)
    if not tiff or len(tiff) < 8:
        return 1
    if tiff[:2] == b"II":
        endian = "<"
    elif tiff[:2] == b"MM":
        endian = ">"
    else:
        return 1
    if struct.unpack(endian + "H", tiff[2:4])[0] != 42:
        return 1

    ifd0_off = struct.unpack(endian + "I", tiff[4:8])[0]
    ifd0 = _read_ifd(tiff, ifd0_off, endian, {0x0112})
    return ifd0.get(0x0112, 1)


# --------------------------------------------------------------------------
# Per-photo metadata
# --------------------------------------------------------------------------

# A filename that opens with digits and a separator: "065-beach-engagement.jpg".
# The digits order the photo, the words after them become its alt text.
NUMBERED_PREFIX = re.compile(r"^(\d+)[-_]+(.*)$")

# A plain word followed by a number, and nothing else: "image64", "photo_7".
WORD_THEN_NUMBER = re.compile(r"^[A-Za-z]+[-_]?(\d+)$")


def sort_number(stem):
    """The number a filename sorts by. Higher sorts earlier, so newest leads.

    Deliberately strict about what counts as a sequence number, because not
    every digit in a filename is one. Two shapes are recognised:

      "065-beach-engagement"  ->  65   (a numeric prefix, the preferred form:
                                        it sets the order *and* leaves words
                                        behind for the alt text)
      "image64"               ->  64   (a word then a number, which is what the
                                        photos carried over from the old grid
                                        are named)

    Anything else returns None and sorts to the end of the page. That is on
    purpose: a camera original like "0K8A9860.JPG" carries a shutter counter,
    not a position in this gallery, and reading it as one put a photo from 2022
    at the top of the page ahead of everything shot since.
    """
    prefix = NUMBERED_PREFIX.match(stem)
    if prefix:
        return int(prefix.group(1))
    word = WORD_THEN_NUMBER.match(stem)
    if word:
        return int(word.group(1))
    return None


def pick_tile(ratio):
    """Closest tile shape, compared in log space so 2:1 and 1:2 are treated evenly."""
    import math
    return min(TILE_RATIOS, key=lambda name: abs(math.log(ratio) - math.log(TILE_RATIOS[name])))


def alt_text(stem):
    # A leading "065-" is ordering information, not description, so drop it
    # before reading the rest of the name as words.
    prefix = NUMBERED_PREFIX.match(stem)
    if prefix:
        stem = prefix.group(2)
    words = re.sub(r"[-_]+", " ", stem).strip()
    if not words or UNDESCRIPTIVE.match(words.replace(" ", "")):
        return None
    words = re.sub(r"\s+", " ", words)
    return words[:1].upper() + words[1:]


def collect():
    if not os.path.isdir(GALLERY_DIR):
        sys.exit(f"ERROR: {GALLERY_DIR} does not exist.")

    photos = []
    problems = []
    no_alt = []
    unnumbered = []
    for name in sorted(os.listdir(GALLERY_DIR)):
        if name.startswith(".") or not name.lower().endswith(SUPPORTED):
            continue
        path = os.path.join(GALLERY_DIR, name)
        with open(path, "rb") as fh:
            data = fh.read()

        size = _png_size(data) if name.lower().endswith(".png") else _jpeg_size(data)
        if not size:
            problems.append(f"{name}: could not read image dimensions; skipped")
            continue
        width, height = size

        # EXIF is still read, but only for orientation: a photo the camera
        # stored sideways has to be measured the way a browser will show it.
        orientation = read_exif_orientation(data) if not name.lower().endswith(".png") else 1
        # Orientations 5-8 mean the browser rotates the photo a quarter turn.
        if orientation in (5, 6, 7, 8):
            width, height = height, width

        stem = os.path.splitext(name)[0]
        alt = alt_text(stem)
        if alt is None:
            no_alt.append(name)

        number = sort_number(stem)
        if number is None:
            unnumbered.append(name)

        photos.append({
            "name": name,
            "src": f"{WEB_PREFIX}/{name}",
            "width": width,
            "height": height,
            "tile": pick_tile(width / height),
            "alt": alt or "",
            "number": number,
        })

    if no_alt:
        problems.append(
            f"{len(no_alt)} photo(s) have no alt text, because their filenames carry no "
            f"description a screen reader could use. Renaming a file is how you set its alt "
            f"text: '065-beach-engagement.jpg' orders the photo at 65 and becomes "
            f"alt=\"Beach engagement\". Affected: " + ", ".join(no_alt)
        )

    if unnumbered:
        problems.append(
            f"{len(unnumbered)} photo(s) have no number in the filename and are placed at "
            f"the end of the page: " + ", ".join(unnumbered)
        )

    # Highest number first, so the newest photo leads the page. Photos with no
    # number at all sort to the very end, alphabetically, rather than landing
    # somewhere arbitrary in the middle.
    photos.sort(key=lambda p: p["name"])
    photos.sort(key=lambda p: (p["number"] is not None, p["number"] or 0), reverse=True)
    return photos, problems


def render(photos):
    lines = [START_MARKER, "        <!-- Generated by tools/build_gallery.py - do not edit by hand. -->"]
    for photo in photos:
        lines.append(f'        <div class="gallery-item {photo["tile"]}">')
        lines.append(
            f'            <img class="thumb placeholder" src="{photo["src"]}"'
            f' data-src="{photo["src"]}" data-image="{photo["src"]}"'
            f' data-title="" alt="{photo["alt"]}"'
            f' width="{photo["width"]}" height="{photo["height"]}" loading="lazy">'
        )
        lines.append("        </div>")
    lines.append("        " + END_MARKER)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="report what would change without writing gallery.html")
    args = parser.parse_args()

    photos, problems = collect()
    if not photos:
        sys.exit(f"ERROR: no images found in {GALLERY_DIR}.")

    with open(GALLERY_HTML, encoding="utf-8") as fh:
        html = fh.read()

    if START_MARKER not in html or END_MARKER not in html:
        sys.exit(f"ERROR: gallery.html is missing the {START_MARKER} / {END_MARKER} markers.")

    pattern = re.compile(
        re.escape(START_MARKER) + ".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )
    updated = pattern.sub(lambda _: render(photos), html, count=1)

    print(f"{len(photos)} photos in {WEB_PREFIX}/")
    print(f"  order: highest filename number first")
    print(f"  first: {photos[0]['name']}   last: {photos[-1]['name']}")
    shapes = {}
    for p in photos:
        shapes[p["tile"]] = shapes.get(p["tile"], 0) + 1
    print("  tiles: " + ", ".join(f"{k}={v}" for k, v in sorted(shapes.items())))

    if problems:
        print()
        for note in problems:
            print(f"NOTE: {note}")

    if args.check:
        print("\nCHANGED" if updated != html else "\nup to date")
        return 0

    if updated == html:
        print("\ngallery.html already up to date.")
        return 0

    with open(GALLERY_HTML, "w", encoding="utf-8") as fh:
        fh.write(updated)
    print("\ngallery.html regenerated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
