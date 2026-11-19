# Sweet-cursors

Fork of [`Sweet` theme](https://github.com/EliverLara/Sweet/tree/nova/kde/cursors) cursors generation

One set of cursors, built for every kind of desktop:

- `Sweet-cursors/cursors`: XCursor, for X11, XWayland and most Wayland compositors, at sizes 24, 30, 32, 36, 48, 60, 64, 72 and 96
- `Sweet-cursors/cursors_scalable`: SVG cursors, which KDE Plasma 6 draws sharp at any size
- `Sweet-cursors-hyprcursor`: SVG cursors for Hyprland's hyprcursor

A size means the same in all three: at 24, a cursor is a 32 px image with the arrow about 20 px tall, as in Breeze and Adwaita.

## Build

Needs Python 3, Inkscape 1.x, `xcursorgen` (xorg-xcursorgen) and, for hyprcursor, `hyprcursor-util` (hyprcursor).

```sh
./build.sh              # XCursor: Sweet-cursors/cursors
./build_scalable.sh     # KDE SVG cursors: Sweet-cursors/cursors_scalable
./build_hyprcursors.sh  # Sweet-cursors-hyprcursor
python3 build.py all    # all three, about 20 seconds
```

## Install

On Arch Linux, the AUR packages `sweet-cursors-git` and `sweet-cursors-hyprcursor-git` build and install them.

Otherwise, copy `Sweet-cursors` (and `Sweet-cursors-hyprcursor`) to `~/.local/share/icons/` or `/usr/share/icons/` and select it in your desktop's settings, or set it in the environment:

```sh
XCURSOR_THEME=Sweet-cursors XCURSOR_SIZE=24
HYPRCURSOR_THEME=Sweet-cursors-hyprcursor HYPRCURSOR_SIZE=24
```

## Editing

Everything is generated from `src/`; `python3 build.py check` checks it without building.

- `src/cursors.svg`: each cursor is drawn over a 32 × 32 rect whose id is the cursor's name, or a frame's name (`wait-01`) for an animation.
- `src/config/NAME.cursor`: one line per frame, `24 X Y x1/ID.png [DELAY_MS]`, with the hotspot (`X Y`) in pixels of the 32 px rect. A new cursor needs a file here.
- `src/cursorList`: `ALIAS CURSOR` per line, the other names a cursor answers to.
