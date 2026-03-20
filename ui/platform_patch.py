# ui/platform_patch.py
import platform
import sys

OS = platform.system()  # "Darwin" = macOS, "Windows" = Windows


def apply_stylesheet_patch(stylesheet: str) -> str:
    """Passt das Stylesheet je nach OS an."""
    if OS == "Darwin":
        return stylesheet.replace(
            "font-family: 'Segoe UI', system-ui, sans-serif;",
            "font-family: 'Helvetica Neue', 'Arial', sans-serif;"
        ).replace(
            "font-size: 13px;",
            "font-size: 12px;"
        )
    return stylesheet  # Windows bleibt unverändert


def get_sidebar_width() -> int:
    return 320 if OS == "Darwin" else 270


def get_button_padding() -> str:
    return "8px 12px" if OS == "Darwin" else "7px 14px"


def style_titlebar(window):
    """Titelleiste einfärben – OS-spezifisch."""
    _set_icon(window)

    if OS == "Windows":
        _style_windows(window)
    elif OS == "Darwin":
        _style_macos(window)


def _set_icon(window):
    from PySide6.QtGui import QIcon, QPainter, QColor, QPixmap
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import QApplication

    svg = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
      <rect width="64" height="64" rx="12" fill="#1e1e2e"/>
      <circle cx="32" cy="20" r="10" fill="none" stroke="#89b4fa" stroke-width="3.5"/>
      <line x1="32" y1="30" x2="32" y2="44" stroke="#89b4fa" stroke-width="3.5" stroke-linecap="round"/>
      <line x1="20" y1="44" x2="44" y2="44" stroke="#89b4fa" stroke-width="3.5" stroke-linecap="round"/>
      <line x1="32" y1="10" x2="38" y2="4" stroke="#a6e3a1" stroke-width="2.5" stroke-linecap="round"/>
      <circle cx="32" cy="20" r="4" fill="#89b4fa" opacity="0.5"/>
    </svg>"""

    renderer = QSvgRenderer(svg)
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    icon = QIcon(pixmap)
    window.setWindowIcon(icon)
    QApplication.instance().setWindowIcon(icon)


def _style_windows(window):
    try:
        import ctypes
        hwnd = int(window.winId())
        color = ctypes.c_uint(0x00_2E_1E_1E)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 35, ctypes.byref(color), ctypes.sizeof(color))
        text_color = ctypes.c_uint(0x00_F4_D6_CD)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 36, ctypes.byref(text_color), ctypes.sizeof(text_color))
    except Exception as e:
        print(f"[Titlebar] Windows DWM: {e}")


def _style_macos(window):
    try:
        from PySide6.QtCore import QTimer
        def _apply():
            try:
                import objc
                from AppKit import NSApplication, NSColor, NSAppearance
                ns_app = NSApplication.sharedApplication()
                ns_win = ns_app.windows()[0]
                ns_win.setTitlebarAppearsTransparent_(True)
                ns_win.setBackgroundColor_(
                    NSColor.colorWithRed_green_blue_alpha_(
                        0x1e/255, 0x1e/255, 0x2e/255, 1.0))
                dark = NSAppearance.appearanceNamed_("NSAppearanceNameDarkAqua")
                ns_win.setAppearance_(dark)
            except Exception as e:
                print(f"[Titlebar] macOS AppKit: {e}")
        QTimer.singleShot(100, _apply)
    except Exception as e:
        print(f"[Titlebar] macOS Setup: {e}")


def activate_app():
    """App in Vordergrund bringen – macOS spezifisch."""
    if OS == "Darwin":
        try:
            from AppKit import NSApplication
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        except Exception:
            pass