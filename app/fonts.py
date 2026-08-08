"""Cross-platform font plumbing for the bundled TTFs and the desktop's own
default UI font.

Before this module the font handling was Windows-only and copy-pasted: five
marquee call sites each did their own AddFontResourceExW + families() scan
guarded by `hasattr(ctypes, "windll")`, so on Linux/macOS the bundled faces
were never even looked for, and the watch asked Tk for "DSEG7 Modern-Regular"
(the Windows *full* name) when the family is actually "DSEG7 Modern".

NOTE for Linux: none of this can work unless Tk was built with Xft. The
python-build-standalone interpreters that uv installs are NOT — their Tk sees
only the ~47 legacy X11 core bitmap fonts and resolves every TrueType request
to "fixed". Check with `len(tkinter.font.families())`: a real Xft build reports
thousands. A distro python (/usr/bin/python3.13) is fine.
"""
import ctypes
import ctypes.util
import logging
import os
import subprocess
import sys

# Family-name candidates per logical font, best first. Names differ per
# platform (GDI reports the full name, fontconfig the family), so every lookup
# goes through resolve_family() rather than hardcoding one spelling.
SEVEN_SEGMENT = ("DSEG7 Modern", "DSEG7 Modern-Regular", "DSEG7Modern-Regular", "dseg7")
WEATHER_ICONS = ("DSEG Weather", "DSEGWeather", "dseg weather")
LCD_MATRIX = ("Tims_8x5_LCD_Matrix", "Tims 8x5 LCD Matrix", "tims", "8x5", "lcd")

_BUNDLED = ("DSEG7Modern-Regular.ttf", "DSEGWeather.ttf", "Tims_8x5_LCD_Matrix.ttf")

# Last-resort families for a Tk with no Xft, where the only thing available is
# the X11 core set. Without these CustomTkinter asks for "Roboto", misses, and
# Tk drops to the "fixed" bitmap face — the chunky pixel text. The URW Type1
# clones below are scalable and vastly closer to a normal UI font.
_FALLBACK_UI = ("Nimbus Sans", "Nimbus Sans L", "Helvetica", "DejaVu Sans", "Liberation Sans")
_FALLBACK_MONO = ("Nimbus Mono L", "Nimbus Mono PS", "Courier 10 Pitch", "Courier", "DejaVu Sans Mono")

_registered = False
_family_cache = {}


def fonts_dir():
    """Locate the bundled fonts/ directory, or None if it isn't there.

    The old call sites used os.path.dirname(__file__) + "/fonts" from inside
    app/mixins/, i.e. app/mixins/fonts/ — a directory that has never existed,
    so os.path.exists() was always False and the registration below it was
    dead code on every platform.
    """
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "fonts"))
    # app/fonts.py -> repo root
    candidates.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts"))
    try:
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(sys.executable)), "fonts"))
    except Exception:
        logging.exception("Suppressed exception")
    for path in candidates:
        if os.path.isdir(path):
            return path
    return None


def _register_windows(paths):
    FR_PRIVATE = 0x10
    added = 0
    for path in paths:
        try:
            added += bool(ctypes.windll.gdi32.AddFontResourceExW(path, FR_PRIVATE, 0))
        except Exception:
            logging.exception("Suppressed exception")
    return added


def _register_fontconfig(paths):
    """POSIX equivalent of AddFontResourceEx: hand the files to fontconfig's
    default config for this process only, which is the same config Tk's Xft
    lookups go through. No files are copied into the user's font directories.
    """
    libname = ctypes.util.find_library("fontconfig")
    if not libname:
        return 0
    try:
        fc = ctypes.CDLL(libname)
    except OSError:
        logging.exception("Suppressed exception")
        return 0
    fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    fc.FcConfigAppFontAddFile.restype = ctypes.c_int
    added = 0
    for path in paths:
        try:
            # NULL config == the current default one, which Tk also uses.
            added += bool(fc.FcConfigAppFontAddFile(None, path.encode("utf-8")))
        except Exception:
            logging.exception("Suppressed exception")
    return added


def register_bundled_fonts():
    """Make the bundled faces visible to Tk for this process. Idempotent.

    Best-effort by design: on a machine where the user (or the launcher, on
    Windows) already installed them system-wide this is a no-op, and if it
    fails the call sites fall back to their default font.
    """
    global _registered
    if _registered:
        return
    _registered = True
    directory = fonts_dir()
    if not directory:
        logging.warning("Bundled fonts directory not found; custom fonts will fall back")
        return
    paths = [os.path.join(directory, name) for name in _BUNDLED]
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        return
    if hasattr(ctypes, "windll"):
        _register_windows(paths)
    else:
        _register_fontconfig(paths)


def resolve_family(candidates, root=None):
    """Return the family name Tk actually knows for the first matching
    candidate, or None when none of them are available.

    Callers must treat None as "use the default font" — asking Tk for a family
    it doesn't have doesn't raise, it silently substitutes something arbitrary,
    which is exactly how the watch ended up rendering in a proportional face.
    """
    import tkinter.font as tkfont
    key = tuple(candidates)
    if key in _family_cache:
        return _family_cache[key]
    register_bundled_fonts()
    try:
        if root is not None:
            root.update_idletasks()
        families = list(tkfont.families())
    except Exception:
        # No Tk root yet — don't cache, the answer would be wrong forever.
        logging.exception("Suppressed exception")
        return None
    if not families:
        return None
    by_lower = {f.lower(): f for f in families}
    result = None
    for candidate in candidates:
        result = by_lower.get(candidate.lower())
        if result:
            break
    if not result:
        # Fuzzy pass for the short aliases ("tims", "8x5", "lcd"), which is how
        # the marquee used to find the LCD face on Windows.
        for candidate in candidates:
            needle = candidate.lower()
            result = next((f for f in families if needle in f.lower()), None)
            if result:
                break
    # Cached because the canvas-heavy screens resolve per drawn item, and
    # families() is a round trip to the interpreter each time.
    _family_cache[key] = result
    return result


def lcd_marquee_font(root=None, size=12):
    """CTkFont for the LCD-matrix music marquee, or a plain default-family font
    of the same size when the face isn't available.

    The five marquee call sites used to inline this, each gated behind
    `hasattr(ctypes, "windll")` — so the family scan never ran off Windows even
    when the font was installed and Tk could see it perfectly well.
    """
    import customtkinter
    family = resolve_family(LCD_MATRIX, root=root)
    if family:
        return customtkinter.CTkFont(size=size, family=family)
    return customtkinter.CTkFont(size=size)


def _gsettings_font(key):
    """Read a desktop font setting, e.g. "'Inter 10'" -> ("Inter", 10)."""
    try:
        out = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", key],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip().strip("'\"")
    except Exception:
        return None, None
    if not out:
        return None, None
    parts = out.split()
    size = None
    if len(parts) > 1 and parts[-1].isdigit():
        size = int(parts[-1])
        parts = parts[:-1]
    # Strip style words the toolkit appends but Tk takes as separate options.
    while parts and parts[-1].lower() in ("regular", "book", "medium", "light", "bold", "italic", "oblique", "condensed"):
        parts.pop()
    family = " ".join(parts)
    return (family or None), size


def system_ui_font():
    """(family, size) of the desktop's UI font, or (None, None) if unknown.

    Only consulted on Linux — Windows and macOS keep CustomTkinter's own
    defaults so their appearance is unchanged.
    """
    if not sys.platform.startswith("linux"):
        return None, None
    return _gsettings_font("font-name")


def system_mono_font():
    """(family, size) of the desktop's monospace font, or a sane per-platform
    default. Replaces the hardcoded "Consolas", which doesn't exist on Linux
    and silently degrades to whatever fontconfig picks."""
    if sys.platform.startswith("linux"):
        family, size = _gsettings_font("monospace-font-name")
        if family:
            return family, size
        return "monospace", None
    if sys.platform == "darwin":
        return "Menlo", None
    return "Consolas", None


def has_xft(root=None):
    """Whether Tk can use modern (fontconfig) fonts at all.

    A Tk built with Xft reports thousands of families; one without reports only
    the ~47 X11 core fonts and silently renders every TrueType request as the
    "fixed" bitmap. The uv / python-build-standalone interpreters are the
    latter, which is why installing a font system-wide changes nothing there.
    """
    import tkinter.font as tkfont
    try:
        return len(tkfont.families()) > 100
    except Exception:
        return False


def mono_family(root=None):
    """Family name only, for the (family, size) tuples the canvas code builds."""
    family, _size = system_mono_font()
    return (resolve_family((family,), root=root)
            or resolve_family(_FALLBACK_MONO, root=root)
            or family)


def apply_system_ui_font(root=None):
    """Point Tk's named fonts and CustomTkinter's default family at the
    desktop's UI font, so the app stops rendering in Tk's own fallback.

    Linux only. Widgets that pass an explicit family are untouched; everything
    that just says CTkFont(size=...) picks this up.

    On a Tk without Xft the desktop font is unreachable, so this falls back to
    the best scalable X11 core font rather than leaving CustomTkinter's "Roboto"
    to miss and land on the "fixed" bitmap face.
    """
    family, size = system_ui_font()
    if not family:
        return None
    resolved = resolve_family((family,), root=root)
    if not resolved:
        resolved = resolve_family(_FALLBACK_UI, root=root)
        if not resolved:
            logging.info("Neither %r nor any fallback UI font is available to Tk", family)
            return None
        logging.warning(
            "Tk has no Xft support, so the desktop font %r (and every bundled TTF) is "
            "unusable; falling back to %r. Only a Tk built against Xft/fontconfig can "
            "fix this — see app/fonts.py.", family, resolved,
        )
        size = None  # the desktop's point size is tuned for a different face

    import tkinter.font as tkfont
    mono = mono_family(root=root)
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont",
                 "TkCaptionFont", "TkSmallCaptionFont", "TkIconFont", "TkTooltipFont"):
        try:
            font = tkfont.nametofont(name)
        except Exception:
            continue  # not every named font exists on every Tk build
        try:
            font.configure(family=resolved, **({"size": size} if size else {}))
        except Exception:
            logging.exception("Suppressed exception")
    try:
        tkfont.nametofont("TkFixedFont").configure(family=mono, **({"size": size} if size else {}))
    except Exception:
        logging.exception("Suppressed exception")

    # CustomTkinter reads its default family from the theme, per platform, and
    # every bare CTkFont(size=...) in the app inherits it.
    # CustomTkinter's default family lives in the theme, and every bare
    # CTkFont(size=...) in the app inherits it. ThemeManager flattens the
    # per-OS dict when it loads a theme file, so the live shape is
    # {"family": ...}; older/unflattened themes keep {"Linux": {"family": ...}}.
    # Handle both — missing this is what left the whole UI on "Roboto", which
    # Tk can't resolve either, hence the bitmap fallback.
    try:
        import customtkinter
        theme = customtkinter.ThemeManager.theme.get("CTkFont", {})
        if "family" in theme:
            theme["family"] = resolved
        for key in ("Linux", "Windows", "macOS"):
            if isinstance(theme.get(key), dict):
                theme[key]["family"] = resolved
    except Exception:
        logging.exception("Suppressed exception")
    logging.info("Using system UI font %r (mono %r)", resolved, mono)
    return resolved
