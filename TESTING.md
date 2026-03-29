# Agentic UI Testing Techniques

This document describes the techniques used for headless visual testing of the ComicCatcher PyQt6 UI during agentic development sessions.

---

## Environment

### Virtual Environment

All Python test scripts use the project venv at `~/cc/test/venv`:

```bash
source ~/cc/test/venv/bin/activate
```

This venv contains PyQt6 and all project dependencies. Always activate it before running any UI test script.

### Virtual Display (Xvfb)

PyQt6 requires a display server. In a headless environment (no physical screen), use Xvfb:

```bash
Xvfb :99 -screen 0 1280x800x24 &
sleep 1
DISPLAY=:99 python /tmp/my_script.py
```

Check if Xvfb is already running before starting a new instance:

```bash
pgrep Xvfb || Xvfb :99 -screen 0 1280x800x24 &
```

---

## Screenshot Patterns

### Pattern 1: Single-widget screenshot

The simplest pattern — create one widget, show it, capture after a short delay, then quit.

```python
import sys, os
sys.path.insert(0, '/home/tony/cc/comiccatcher')
os.chdir('/home/tony/cc/comiccatcher')

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

app = QApplication(sys.argv)
from ui.theme_manager import ThemeManager
from ui.views.settings import SettingsView
from config import ConfigManager

config = ConfigManager()
ThemeManager.apply_theme(app, "dark")

view = SettingsView(config)
view.resize(800, 600)
view.show()

def capture():
    app.primaryScreen().grabWindow(view.winId()).save('/tmp/settings_dark.png')
    app.quit()

QTimer.singleShot(400, capture)
app.exec()
```

Key points:
- Apply the theme **before** creating the widget, so all icons and colors initialize with the correct theme
- Use `QTimer.singleShot` to defer capture until after the event loop has processed the initial paint
- 300–500ms delay is usually sufficient; use more if the view loads data asynchronously

### Pattern 2: Multi-theme loop (single reused window)

Efficient for capturing the same view across all four themes without recreating widgets.

```python
themes = ['light', 'dark', 'oled', 'blue']
idx = [0]

view = SettingsView(config)
view.resize(800, 600)
view.show()

def next_theme():
    if idx[0] >= len(themes):
        app.quit()
        return
    t = themes[idx[0]]
    ThemeManager.apply_theme(app, t)
    # Force all widgets to re-evaluate the new stylesheet
    for widget in app.allWidgets():
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
    QTimer.singleShot(300, lambda: capture(t))

def capture(t):
    app.primaryScreen().grabWindow(view.winId()).save(f'/tmp/view_{t}.png')
    idx[0] += 1
    QTimer.singleShot(50, next_theme)

QTimer.singleShot(200, next_theme)
app.exec()
```

**Caveat:** Icons set programmatically during `__init__` (e.g. via `item.setIcon(ThemeManager.get_icon(...))`) are not automatically refreshed when the stylesheet changes. Call the relevant refresh methods manually after each theme switch, or use Pattern 3 for accurate icon rendering.

### Pattern 3: Per-theme separate instances (accurate icon colors)

The most accurate approach. Applies the theme first, then creates a fresh widget so all icons initialize with the correct color.

```python
themes = ['light', 'dark', 'oled', 'blue']
idx = [0]
win = [None]

def next_theme():
    if idx[0] >= len(themes):
        app.quit()
        return
    t = themes[idx[0]]
    if win[0]:
        win[0].close()
    ThemeManager.apply_theme(app, t)
    w = SettingsView(config)
    win[0] = w
    w.resize(800, 600)
    w.show()
    QTimer.singleShot(400, lambda: capture(t))

def capture(t):
    app.primaryScreen().grabWindow(win[0].winId()).save(f'/tmp/view_{t}.png')
    idx[0] += 1
    QTimer.singleShot(100, next_theme)

QTimer.singleShot(200, next_theme)
app.exec()
```

### Pattern 4: Simulating live theme switching

Tests what happens when the user switches themes at runtime — the most realistic test for live-switch bugs (e.g. GroupBox backgrounds not updating, icons staying the wrong color).

```python
ThemeManager.apply_theme(app, "light")
view = SettingsView(config)
view.show()

def switch_to_dark():
    ThemeManager.apply_theme(app, "dark")
    for widget in app.allWidgets():
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
    # Also refresh any programmatically-set icons
    view.feed_management.refresh_feeds()
    QTimer.singleShot(400, capture_dark)

def capture_dark():
    app.primaryScreen().grabWindow(view.winId()).save('/tmp/switched_dark.png')
    app.quit()

QTimer.singleShot(300, switch_to_dark)
app.exec()
```

This pattern was used to diagnose and verify the fix for the dark-mode GroupBox background regression that appeared only after switching from light mode.

---

## Capturing the Full App Window

For testing the main `MainWindow` (sidebar, toolbar, navigation):

```python
from ui.app_layout import MainWindow
from config import ConfigManager

config = ConfigManager()
w = MainWindow(config)
w.resize(900, 650)
w.show()

# Apply theme AFTER show so all widgets exist
def do_apply():
    ThemeManager.apply_theme(app, "oled")
    for widget in app.allWidgets():
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
    QTimer.singleShot(500, capture)

QTimer.singleShot(200, do_apply)
```

Applying the theme after `show()` (rather than before) is necessary for `MainWindow` because it calls `_apply_theme()` internally during `__init__`. Post-show application ensures the full widget tree exists and is polished with the target theme.

---

## Capturing Popup Menus

Menus close immediately if focus is lost, so capture must happen while the menu is open:

```python
def show_menu():
    menu.popup(win.mapToGlobal(QPoint(10, 10)))
    QTimer.singleShot(400, capture)

def capture():
    # Grab the entire screen — the menu is a top-level window
    app.primaryScreen().grabWindow(0).save('/tmp/menu.png')
    menu.close()
```

Use `grabWindow(0)` (the root window) rather than a specific widget's `winId()` to capture floating popups like `QMenu`.

---

## Handling Async Code in Test Scripts

Views that use `asyncio.create_task` at construction time (e.g. `FeedManagementView`) will crash in a plain `QApplication` context because there is no running event loop. Patch `asyncio.create_task` to be a no-op before importing these views:

```python
import asyncio
_orig = asyncio.create_task
def _safe(coro, **kw):
    try:
        return _orig(coro, **kw)
    except RuntimeError:
        coro.close()
        return None
asyncio.create_task = _safe
```

Apply this patch at the top of the script, before any project imports.

---

## Reading Screenshots

After saving screenshots to `/tmp`, use the `Read` tool to view them. The tool renders images inline, allowing direct visual inspection without leaving the session.

```
Read /tmp/settings_dark.png
```

Compare multiple themes side-by-side by reading them sequentially and noting differences in:
- GroupBox background colors (dark/OLED should not show white/light-gray boxes)
- Icon visibility (SVG icons are colored at runtime via `ThemeManager.get_icon()`)
- Text contrast (nav labels, dim text on dark sidebars)
- Button states (normal, hover, checked, disabled)
- Menu separators and item backgrounds
- Radio button and checkbox indicators

---

## Common Issues and Fixes

| Symptom | Cause | Fix |
|---|---|---|
| Icons appear white in light mode | Icons set before theme applied | Apply theme before creating widget (Pattern 3) |
| GroupBox shows white background in dark mode | No `background-color` on `QGroupBox` CSS rule | Add `background-color: {theme['bg_main']}` to `QGroupBox` rule |
| Live theme switch leaves stale colors | Qt caches widget style | Call `unpolish/polish/update` on all widgets after stylesheet change |
| Radio button circles invisible | No `QRadioButton::indicator` CSS rule | Add explicit indicator rules with border and background states |
| Menu separator invisible in dark mode | Separator color same as background | Use `text_dim` instead of `border` for `QMenu::separator` background |
| `ModuleNotFoundError` in test script | Wrong working directory | Add `sys.path.insert(0, ...)` and `os.chdir(...)` at script top |
| `RuntimeError: no running event loop` | `asyncio.create_task` in widget `__init__` | Patch `asyncio.create_task` before imports (see above) |
| App crashes on `Aborted (core dumped)` | Xvfb not running or xcb plugin missing | Start Xvfb first; ensure `DISPLAY=:99` is set |
