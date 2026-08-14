#!/usr/bin/env python3
"""Regenerate gallery-images.json from the files in images/Portfolio/.

Writes each photo's real pixel dimensions alongside its filename so gallery.html
can lay out the masonry grid (and reserve each tile's space) before any image
has finished downloading. Dimensions are read straight out of the JPEG/PNG
headers using only the standard library, so this runs unchanged on macOS and on
the GitHub Actions runner.

Usage: python3 update-gallery.py
"""

import json
import os
import re
import struct
import sys
from datetime import datetime, timezone

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTO_DIR = os.path.join(REPO_DIR, "images", "Portfolio")
OUTPUT = os.path.join(REPO_DIR, "gallery-images.json")

EXTENSIONS = (".jpg", ".jpeg", ".png")

# Files that live in images/Portfolio/ but are site furniture rather than
# portfolio photos — the homepage collage, the About page portrait, and a stray
# duplicate of image23.jpg. Add a filename here to hide it from the gallery.
EXCLUDED = {
    "collage.jpg",
    "collage1.png",
    "jellybelly.png",
    "Nicky-Portrait.jpg",
    "Nicky-Portrait-Pic.png",
    "image23-copy.jpg",
}

# JPEG start-of-frame markers carry the image dimensions. 0xC4 (define Huffman
# table), 0xC8 (reserved) and 0xCC (define arithmetic coding) share the range
# but are not frame headers.
SOF_MARKERS = {
    0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
    0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
}


def png_size(f):
    """Read width/height from a PNG's IHDR chunk."""
    f.seek(16)
    return struct.unpack(">II", f.read(8))


def jpeg_exif_orientation(segment):
    """Pull the EXIF orientation tag out of an APP1 segment, or None."""
    if not segment.startswith(b"Exif\x00\x00"):
        return None
    tiff = segment[6:]
    if len(tiff) < 8:
        return None
    endian = "<" if tiff[:2] == b"II" else ">" if tiff[:2] == b"MM" else None
    if endian is None:
        return None
    (ifd_offset,) = struct.unpack(endian + "I", tiff[4:8])
    if ifd_offset + 2 > len(tiff):
        return None
    (entry_count,) = struct.unpack(endian + "H", tiff[ifd_offset:ifd_offset + 2])
    for i in range(entry_count):
        entry = ifd_offset + 2 + i * 12
        if entry + 12 > len(tiff):
            break
        tag, fmt = struct.unpack(endian + "HH", tiff[entry:entry + 4])
        if tag == 0x0112 and fmt == 3:  # Orientation, SHORT
            (value,) = struct.unpack(endian + "H", tiff[entry + 8:entry + 10])
            return value
    return None


def jpeg_size(f):
    """Read width/height from a JPEG, honouring any EXIF orientation tag.

    Cameras often store a portrait photo as landscape pixels plus a "rotate me"
    orientation flag. Browsers apply that rotation, so the gallery has to use
    the rotated dimensions or every such tile would be shaped wrong.
    """
    f.seek(2)  # skip the SOI marker
    orientation = None
    while True:
        byte = f.read(1)
        if not byte:
            raise ValueError("no JPEG frame header found")
        if byte != b"\xff":
            continue  # resync on the next marker
        marker_byte = f.read(1)
        while marker_byte == b"\xff":  # markers may be padded with fill bytes
            marker_byte = f.read(1)
        if not marker_byte:
            raise ValueError("no JPEG frame header found")
        marker = marker_byte[0]
        if marker in (0x00, 0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue  # standalone markers and stuffed bytes carry no payload
        (length,) = struct.unpack(">H", f.read(2))
        payload = f.read(length - 2)
        if marker == 0xE1 and orientation is None:
            orientation = jpeg_exif_orientation(payload)
        elif marker in SOF_MARKERS:
            height, width = struct.unpack(">HH", payload[1:5])
            if orientation in (5, 6, 7, 8):
                width, height = height, width
            return width, height
        # Anything else (comments, quantisation tables, ...) is skipped; the
        # frame header always precedes the compressed scan data.


def image_size(path):
    with open(path, "rb") as f:
        if f.read(8) == b"\x89PNG\r\n\x1a\n":
            return png_size(f)
        f.seek(0)
        if f.read(2) == b"\xff\xd8":
            return jpeg_size(f)
    raise ValueError("unrecognised image format")


def newest_first(name):
    """Sort key putting the highest-numbered photos first (image64 before image9).

    Filenames are mostly imageNN.jpg, so the number is a rough stand-in for how
    recently the photo was added — newest work belongs at the top of the page.
    Splitting on digit runs keeps image9 below image64 instead of above it, the
    way a plain alphabetical sort would order them.
    """
    parts = re.split(r"(\d+)", name.lower())
    return [(1, int(p)) if p.isdigit() else (0, p) for p in parts]


def main():
    if not os.path.isdir(PHOTO_DIR):
        sys.exit("No images/Portfolio/ folder found at %s" % PHOTO_DIR)

    names = sorted(
        (
            name
            for name in os.listdir(PHOTO_DIR)
            if name.lower().endswith(EXTENSIONS)
            and name not in EXCLUDED
            and not name.startswith(".")
        ),
        key=newest_first,
        reverse=True,
    )

    images = []
    for name in names:
        try:
            width, height = image_size(os.path.join(PHOTO_DIR, name))
        except (OSError, ValueError, struct.error) as err:
            print("  skipped %s (%s)" % (name, err), file=sys.stderr)
            continue
        images.append({"src": name, "width": width, "height": height})

    if not images:
        sys.exit("No readable images found in images/Portfolio/")

    data = {
        "images": images,
        "count": len(images),
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with open(OUTPUT, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    print("Gallery updated: %d photos. Push to GitHub to publish." % len(images))


if __name__ == "__main__":
    main()
