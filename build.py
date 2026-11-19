#!/usr/bin/env python3
"""Builds the Sweet cursor themes from src/.

    build.py xcursor     Sweet-cursors/cursors and index.theme (needs inkscape, xcursorgen)
    build.py scalable    Sweet-cursors/cursors_scalable, KDE's SVG cursors (needs inkscape)
    build.py hyprcursor  Sweet-cursors-hyprcursor (needs inkscape, hyprcursor-util)
    build.py all         all three
    build.py check       only checks src/, which every build does first

The sources, each cursor's hotspot and aliases written once for every format:

    src/cursors.svg     every cursor is the art inside a 32x32 rect whose id is its name
                        (`default`) or, for an animation, the name of a frame (`wait-01`)
    src/config/NAME.cursor
                        one line per frame: `24 HOTSPOT_X HOTSPOT_Y x1/ID.png [DELAY_MS]`,
                        the hotspot in pixels of the 32 px rect
    src/cursorList      `ALIAS CURSOR` per line: other names a cursor answers to; CURSOR may
                        be another alias
    src/index.theme, src/hyprcursors/manifest.toml

Sizes follow the XCursor convention Breeze and Adwaita share: at size 24 the 32 px rect is
a 32 px image (the art in it is about 20 px tall), and it scales with the size.
"""

import json
import math
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
SVG = os.path.join(SRC, "cursors.svg")
BUILD = os.path.join(ROOT, "build")

# Cursor sizes in the XCursor theme: the sizes GNOME and KDE offer, and Breeze's steps of 6.
SIZES = [24, 30, 32, 36, 48, 60, 64, 72, 96]
# The size at which the source rect (SIDE px) is drawn 1:1.
NOMINAL = 24
SIDE = 32


def die(message):
    sys.exit(f"error: {message}")


def need(tool):
    if shutil.which(tool) is None:
        die(f"{tool} must be installed")


class Frame:
    def __init__(self, id, hotspot, delay):
        self.id = id
        self.hotspot = hotspot
        self.delay = delay


def read_cursors():
    """{name: [Frame]}, from src/config."""
    cursors = {}
    config = os.path.join(SRC, "config")
    for file in sorted(os.listdir(config)):
        if not file.endswith(".cursor"):
            continue
        name = file[: -len(".cursor")]
        frames = []
        with open(os.path.join(config, file)) as f:
            for number, line in enumerate(f, 1):
                fields = line.split()
                if not fields:
                    continue
                where = f"src/config/{file}:{number}"
                if len(fields) not in (4, 5) or fields[0] != str(NOMINAL):
                    die(f"{where}: expected `{NOMINAL} X Y x1/ID.png [DELAY]`")
                x, y = int(fields[1]), int(fields[2])
                if not (0 <= x < SIDE and 0 <= y < SIDE):
                    die(f"{where}: hotspot {x},{y} outside the {SIDE} px rect")
                id = os.path.splitext(os.path.basename(fields[3]))[0]
                delay = int(fields[4]) if len(fields) == 5 else None
                frames.append(Frame(id, (x, y), delay))
        if not frames:
            die(f"src/config/{file} has no frames")
        if len(frames) > 1 and any(frame.delay is None for frame in frames):
            die(f"src/config/{file}: every frame of an animation needs a delay")
        cursors[name] = frames
    return cursors


def read_aliases(cursors):
    """{alias: cursor}, each alias resolved to the cursor it ends at."""
    targets = {}
    with open(os.path.join(SRC, "cursorList")) as f:
        for number, line in enumerate(f, 1):
            fields = line.split()
            if not fields:
                continue
            where = f"src/cursorList:{number}"
            if len(fields) != 2:
                die(f"{where}: expected `ALIAS CURSOR`")
            alias, target = fields
            if alias in cursors:
                die(f"{where}: {alias} is a cursor itself, not an alias")
            if alias in targets:
                die(f"{where}: {alias} is listed twice")
            targets[alias] = target
    resolved = {}
    for alias in targets:
        seen = [alias]
        target = targets[alias]
        while target not in cursors:
            if target not in targets:
                die(f"src/cursorList: {alias} leads to {target}, which is no cursor")
            if target in seen:
                die(f"src/cursorList: {alias} leads to a loop: {' -> '.join(seen + [target])}")
            seen.append(target)
            target = targets[target]
        resolved[alias] = target
    return resolved


def svg_ids():
    return set(re.findall(r'\sid="([^"]+)"', open(SVG, encoding="utf-8").read()))


def check():
    cursors = read_cursors()
    aliases = read_aliases(cursors)
    ids = svg_ids()
    for name, frames in cursors.items():
        for frame in frames:
            if frame.id not in ids:
                die(f"src/config/{name}.cursor: no `{frame.id}` in src/cursors.svg")
    return cursors, aliases


def theme_name():
    with open(os.path.join(SRC, "index.theme")) as f:
        for line in f:
            if line.startswith("Name="):
                return line[len("Name=") :].strip().replace(" ", "_")
    die("src/index.theme has no Name")


def all_frames(cursors):
    return [frame for frames in cursors.values() for frame in frames]


def image_side(size):
    """The image side for a cursor size: the source rect scaled from NOMINAL."""
    return round(size * SIDE / NOMINAL)


def scaled(hotspot, side):
    """The hotspot in a `side` px image, rounded as hyprcursor rounds it, so every format
    puts it on the same pixel."""
    return min(side - 1, math.floor(hotspot * side / SIDE + 0.5))


def inkscape(actions):
    """Runs inkscape once on the source with `actions`, each a list of action strings."""
    need("inkscape")
    os.makedirs(BUILD, exist_ok=True)
    # A file: hundreds of exports are too long for one command line.
    script = os.path.join(BUILD, "actions")
    with open(script, "w") as f:
        f.write(";\n".join(a for action in actions for a in action) + "\n")
    result = subprocess.run(
        ["inkscape", SVG, f"--actions-file={script}"], capture_output=True, text=True
    )
    if result.returncode != 0:
        die(f"inkscape failed:\n{result.stderr}")


def export_png(id, side, path):
    # Not export-id-only: the rect is only the frame, the art is drawn around it.
    return [
        "export-type:png",
        f"export-id:{id}",
        f"export-width:{side}",
        f"export-height:{side}",
        "export-background-opacity:0",
        f"export-filename:{path}",
        "export-do",
    ]


def export_svg(id, path):
    return [
        "export-type:svg",
        "export-plain-svg",
        f"export-id:{id}",
        f"export-filename:{path}",
        "export-do",
    ]


def fresh(path):
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path)


# --- SVG cursors -----------------------------------------------------------------------

NAMESPACES = {
    "": "http://www.w3.org/2000/svg",
    "xlink": "http://www.w3.org/1999/xlink",
    "inkscape": "http://www.inkscape.org/namespaces/inkscape",
    "sodipodi": "http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "cc": "http://creativecommons.org/ns#",
    "dc": "http://purl.org/dc/elements/1.1/",
}
for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)


def query_boxes():
    """{id: (x, y, w, h)}: the visual bounding box of every element of the source."""
    need("inkscape")
    result = subprocess.run(["inkscape", "--query-all", SVG], capture_output=True, text=True)
    if result.returncode != 0:
        die(f"inkscape --query-all failed:\n{result.stderr}")
    boxes = {}
    for line in result.stdout.splitlines():
        fields = line.split(",")
        if len(fields) == 5:
            boxes[fields[0]] = tuple(float(v) for v in fields[1:])
    return boxes


def crop(path, frame, boxes):
    """Leaves in the exported SVG at `path` only what can show inside the rect `frame`.

    An export of one cursor is the whole sheet, only framed on that cursor; this removes
    every element whose bounding box misses the frame, then the definitions nothing uses.
    """
    fx, fy, fw, fh = boxes[frame]

    def outside(box):
        x, y, w, h = box
        return x >= fx + fw or x + w <= fx or y >= fy + fh or y + h <= fy

    def inside(box):
        x, y, w, h = box
        return x >= fx and y >= fy and x + w <= fx + fw and y + h <= fy + fh

    tree = ET.parse(path)
    root = tree.getroot()
    svg = "{%s}" % NAMESPACES[""]

    def prune(parent):
        for child in list(parent):
            box = boxes.get(child.get("id"))
            if box is None:
                prune(child)
            elif outside(box):
                parent.remove(child)
            elif not inside(box):
                prune(child)

    defs = [child for child in root if child.tag == svg + "defs"]
    for child in root:
        if child.tag not in (svg + "defs", svg + "metadata"):
            prune(child)

    # Definitions used by what's left, and by the definitions they use.
    reference = re.compile(r'url\(#([^)]+)\)|href="#([^"]+)"')

    def references(element):
        text = ET.tostring(element, encoding="unicode")
        return {a or b for a, b in reference.findall(text)}

    used = set()
    for child in root:
        if child.tag != svg + "defs":
            used |= references(child)
    by_id = {d.get("id"): d for defs_ in defs for d in defs_ if d.get("id")}
    todo = list(used)
    while todo:
        definition = by_id.get(todo.pop())
        if definition is not None:
            for ref in references(definition) - used:
                used.add(ref)
                todo.append(ref)
    for defs_ in defs:
        for definition in list(defs_):
            if definition.get("id") not in used:
                defs_.remove(definition)
    tree.write(path, encoding="UTF-8", xml_declaration=True)


_exported = {}


def export_svgs(cursors, directory):
    """Every frame as a cropped SVG, `directory/ID.svg`; {id: path}. Once per run: the
    export is most of the time of an SVG build."""
    if directory in _exported:
        return _exported[directory]
    print(f"Exporting {len(all_frames(cursors))} SVGs...")
    fresh(directory)
    paths = {frame.id: os.path.join(directory, f"{frame.id}.svg") for frame in all_frames(cursors)}
    inkscape(export_svg(id, path) for id, path in paths.items())
    boxes = query_boxes()
    for id, path in paths.items():
        crop(path, id, boxes)
    _exported[directory] = paths
    return paths


def link_aliases(directory, aliases):
    for alias, cursor in sorted(aliases.items()):
        os.symlink(cursor, os.path.join(directory, alias))


# --- builds ----------------------------------------------------------------------------


def build_xcursor(cursors, aliases):
    need("xcursorgen")
    output = os.path.join(ROOT, theme_name())
    png = os.path.join(BUILD, "png")
    fresh(png)
    for size in SIZES:
        os.makedirs(os.path.join(png, str(size)))  # inkscape makes no directories
    print(f"Exporting {len(all_frames(cursors))} images at sizes {', '.join(map(str, SIZES))}...")
    inkscape(
        export_png(frame.id, image_side(size), os.path.join(png, str(size), f"{frame.id}.png"))
        for size in SIZES
        for frame in all_frames(cursors)
    )

    print("Generating cursors...")
    cursors_dir = os.path.join(output, "cursors")
    fresh(cursors_dir)
    configs = os.path.join(BUILD, "xcursor-config")
    fresh(configs)
    for name, frames in cursors.items():
        lines = []
        for size in SIZES:
            side = image_side(size)
            for frame in frames:
                x, y = (scaled(v, side) for v in frame.hotspot)
                line = f"{size} {x} {y} {size}/{frame.id}.png"
                if frame.delay is not None:
                    line += f" {frame.delay}"
                lines.append(line)
        config = os.path.join(configs, f"{name}.cursor")
        with open(config, "w") as f:
            f.write("\n".join(lines) + "\n")
        result = subprocess.run(
            ["xcursorgen", "-p", png, config, os.path.join(cursors_dir, name)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            die(f"xcursorgen failed for {name}:\n{result.stderr}")
    link_aliases(cursors_dir, aliases)
    shutil.copy(os.path.join(SRC, "index.theme"), os.path.join(output, "index.theme"))
    print(f"{output}/cursors: {len(cursors)} cursors, {len(aliases)} aliases")


def build_scalable(cursors, aliases):
    output = os.path.join(ROOT, theme_name())
    svgs = export_svgs(cursors, os.path.join(BUILD, "svg"))

    scalable = os.path.join(output, "cursors_scalable")
    fresh(scalable)
    for name, frames in cursors.items():
        directory = os.path.join(scalable, name)
        os.makedirs(directory)
        metadata = []
        for frame in frames:
            shutil.copy(svgs[frame.id], directory)
            # KWin reads the hotspot in pixels of the SVG at nominal_size, and scales it.
            entry = {
                "filename": f"{frame.id}.svg",
                "hotspot_x": frame.hotspot[0],
                "hotspot_y": frame.hotspot[1],
                "nominal_size": NOMINAL,
            }
            if frame.delay is not None:
                entry["delay"] = frame.delay
            metadata.append(entry)
        with open(os.path.join(directory, "metadata.json"), "w") as f:
            json.dump(metadata, f, indent=4)
            f.write("\n")
    link_aliases(scalable, aliases)
    shutil.copy(os.path.join(SRC, "index.theme"), os.path.join(output, "index.theme"))
    print(f"{scalable}: {len(cursors)} cursors, {len(aliases)} aliases")


def build_hyprcursor(cursors, aliases):
    need("hyprcursor-util")
    svgs = export_svgs(cursors, os.path.join(BUILD, "svg"))

    source = os.path.join(BUILD, "hyprcursor")
    fresh(source)
    shutil.copy(os.path.join(SRC, "hyprcursors", "manifest.toml"), source)
    manifest = open(os.path.join(source, "manifest.toml")).read()
    directory = re.search(r'cursors_directory\s*=\s*"([^"]+)"', manifest).group(1)
    name = re.search(r'name\s*=\s*"([^"]+)"', manifest).group(1)
    overrides = {}
    for alias, cursor in aliases.items():
        overrides.setdefault(cursor, []).append(alias)
    for cursor, frames in cursors.items():
        shape = os.path.join(source, directory, cursor)
        os.makedirs(shape)
        x, y = frames[0].hotspot
        lines = [
            "resize_algorithm = bilinear",
            # hyprcursor: fractions of the image, which it draws at size / nominal_size.
            f"hotspot_x = {x / SIDE:g}",
            f"hotspot_y = {y / SIDE:g}",
            f"nominal_size = {NOMINAL / SIDE:g}",
            "",
        ]
        for frame in frames:
            shutil.copy(svgs[frame.id], shape)
            delay = f", {frame.delay}" if frame.delay is not None else ""
            lines.append(f"define_size = 0, {frame.id}.svg{delay}")
        if any(frame.hotspot != (x, y) for frame in frames):
            die(f"{cursor}: hyprcursor needs one hotspot for all frames")
        lines.append("")
        lines += [f"define_override = {alias}" for alias in sorted(overrides.get(cursor, []))]
        with open(os.path.join(shape, "meta.hl"), "w") as f:
            f.write("\n".join(lines) + "\n")

    out = os.path.join(BUILD, "hyprcursor-out")
    fresh(out)
    result = subprocess.run(
        ["hyprcursor-util", "-c", source, "-o", out], capture_output=True, text=True
    )
    built = os.path.join(out, f"theme_{name}")
    if result.returncode != 0 or not os.path.isdir(built):
        die(f"hyprcursor-util failed:\n{result.stdout}{result.stderr}")
    output = os.path.join(ROOT, name)
    shutil.rmtree(output, ignore_errors=True)
    shutil.move(built, output)
    print(f"{output}: {len(cursors)} cursors, {len(aliases)} aliases")


def main():
    targets = {
        "xcursor": [build_xcursor],
        "scalable": [build_scalable],
        "hyprcursor": [build_hyprcursor],
        "all": [build_xcursor, build_scalable, build_hyprcursor],
        "check": [],
    }
    if len(sys.argv) != 2 or sys.argv[1] not in targets:
        sys.exit(__doc__)
    cursors, aliases = check()
    for build in targets[sys.argv[1]]:
        build(cursors, aliases)
    if not targets[sys.argv[1]]:
        print(f"src/ is consistent: {len(cursors)} cursors, {len(aliases)} aliases")


if __name__ == "__main__":
    main()
