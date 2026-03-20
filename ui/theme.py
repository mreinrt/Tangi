"""
Theme definitions and application functions
"""

from PyQt6.QtGui import QPalette, QColor, QFont
from PyQt6.QtWidgets import QWidget, QApplication
import logging

logger = logging.getLogger(__name__)

# ---------- THEME DEFINITIONS ----------
DARK_THEME = {
    "background": "#2b2b2b",
    "text": "#00ff00",
    "menu_text": "#00ff00",
    "chat_bg": "#000000",
    "chat_text": "#00ff00",
    "button_bg": "#444444",
    "button_hover": "#555555",
    "button_pressed": "#333333",
    "border": "#888888",
    "slider_groove": "#444444",
    "slider_handle": "#222222",
    "placeholder": "#888888",
    "radio_bg": "#333333",
    "radio_text": "#00ff00",
    "radio_hover": "#444444",
    "checkbox_bg": "#333333",
    "checkbox_text": "#00ff00",
    "checkbox_hover": "#444444",
    "font_family": "DejaVu Sans Mono",
    "font_size": 10,
    "code_bg": "#969696",
    "code_text": "#00ff00",
}

LIGHT_THEME = {
    "background": "#ffffff",
    "text": "#000000",
    "menu_text": "#000000",
    "chat_bg": "#f0f0f0",
    "chat_text": "#000000",
    "button_bg": "#DAD3D3D3",
    "button_hover": "#8A8A8A",
    "button_pressed": "#ccc",
    "border": "#888888",
    "slider_groove": "#ddd",
    "slider_handle": "#666666",
    "placeholder": "#888888",
    "radio_bg": "#eeeeee",
    "radio_text": "#000000",
    "radio_hover": "#dddddd",
    "checkbox_bg": "#eeeeee",
    "checkbox_text": "#000000",
    "checkbox_hover": "#dddddd",
    "font_family": "DejaVu Sans Mono",
    "font_size": 10,
    "code_bg": "#dbdbdbff",
    "code_text": "#333333",
}

THEMES = {"dark": DARK_THEME, "light": LIGHT_THEME}
CURRENT_THEME = "dark"

# Cache for stylesheets
_STYLESHEET_CACHE = {}


def set_theme(name: str):
    """Set the current theme by name"""
    global CURRENT_THEME
    if name.lower() in THEMES:
        CURRENT_THEME = name.lower()
        logger.info(f"Theme changed to: {CURRENT_THEME}")
        _STYLESHEET_CACHE.clear()


def _generate_stylesheet(theme):
    """Generate and cache stylesheet for a theme"""
    theme_name = theme.get("name", CURRENT_THEME)
    
    if theme_name in _STYLESHEET_CACHE:
        return _STYLESHEET_CACHE[theme_name]

    text_color = theme["text"]
    border_color = theme["border"]
    background_color = theme["background"]
    chat_bg_color = theme["chat_bg"]

    button_bg_color = theme["button_bg"]
    button_hover_color = theme["button_hover"]
    button_pressed_color = theme["button_pressed"]

    placeholder_color = theme["placeholder"]

    slider_handle_color = theme["slider_handle"]
    slider_groove_color = theme["slider_groove"]

    radio_bg_color = theme["radio_bg"]
    radio_text_color = theme["radio_text"]
    radio_hover_color = theme["radio_hover"]

    checkbox_bg_color = theme["checkbox_bg"]
    checkbox_text_color = theme["checkbox_text"]
    checkbox_hover_color = theme["checkbox_hover"]

    code_bg = theme["code_bg"]
    code_text = theme["code_text"]

    stylesheet = f"""
        * {{
            font-family: '{theme["font_family"]}';
            font-size: {theme["font_size"]}pt;
        }}

        QWidget {{
            color: {text_color};
            background-color: {background_color};
        }}

        QTextEdit, QTextBrowser, QPlainTextEdit {{
            background-color: {chat_bg_color};
            color: {text_color};
            border: 1px solid {border_color};
            selection-background-color: {button_hover_color};
        }}

        QTextEdit::placeholder, QPlainTextEdit::placeholder {{
            color: {placeholder_color};
        }}

        QPushButton {{
            background-color: {button_bg_color};
            color: {text_color};
            border: 1px solid {border_color};
            padding: 5px 10px;
            border-radius: 3px;
        }}

        QPushButton:hover {{
            background-color: {button_hover_color};
        }}

        QPushButton:pressed {{
            background-color: {button_pressed_color};
        }}

        QPushButton:disabled {{
            background-color: #333;
            color: #666;
        }}

        QMenuBar {{
            background-color: {background_color};
            color: {text_color};
        }}

        QMenuBar::item:selected {{
            background-color: {button_hover_color};
        }}

        QMenu {{
            background-color: {background_color};
            color: {text_color};
            border: 1px solid {border_color};
        }}

        QMenu::item:selected {{
            background-color: {button_hover_color};
        }}

        QLineEdit, QComboBox {{
            background-color: {button_bg_color};
            color: {text_color};
            border: 1px solid {border_color};
            padding: 5px;
        }}

        QGroupBox {{
            color: {text_color};
            border: 1px solid {border_color};
            margin-top: 10px;
            padding-top: 10px;
            font-weight: bold;
        }}

        QSlider::groove:horizontal {{
            border: 1px solid {border_color};
            height: 8px;
            background: {slider_groove_color};
            border-radius: 4px;
        }}

        QSlider::handle:horizontal {{
            background: {slider_handle_color};
            border: 1px solid {border_color};
            width: 18px;
            margin: -5px 0;
            border-radius: 9px;
        }}

        QLabel {{
            color: {text_color};
        }}

        QScrollBar:vertical, QScrollBar:horizontal {{
            background-color: {background_color};
            border: 1px solid {border_color};
        }}

        QScrollBar::handle {{
            background-color: {button_bg_color};
            border: 1px solid {border_color};
        }}

        QScrollBar::handle:hover {{
            background-color: {button_hover_color};
        }}

        QRadioButton {{
            color: {radio_text_color};
            padding: 5px;
        }}

        QRadioButton::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 8px;
            border: 2px solid {border_color};
            background-color: {radio_bg_color};
        }}

        QRadioButton::indicator:checked {{
            background-color: {radio_text_color};
        }}

        QCheckBox {{
            color: {checkbox_text_color};
            padding: 5px;
        }}

        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border: 2px solid {border_color};
            background-color: {checkbox_bg_color};
        }}

        QCheckBox::indicator:checked {{
            background-color: {checkbox_text_color};
        }}

        QToolTip {{
            background-color: {background_color};
            color: {text_color};
            border: 1px solid {border_color};
            padding: 5px;
        }}

        /* ===== ENHANCED CODE BLOCK STYLES ===== */
        pre {{
            background-color: {code_bg} !important;
            border: 1px solid {border_color} !important;
            border-radius: 5px !important;
            padding: 12px !important;
            margin: 10px 0 !important;
            overflow-x: auto !important;
            font-family: '{theme["font_family"]}', monospace !important;
            font-size: {theme["font_size"]}pt !important;
            color: {code_text} !important;
            white-space: pre-wrap !important;
            word-wrap: break-word !important;
            overflow-wrap: break-word !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
            isolation: isolate !important;
            position: relative !important;
            z-index: 1 !important;
        }}

        code {{
            background-color: {code_bg} !important;
            color: {code_text} !important;
            padding: 2px 4px !important;
            border-radius: 3px !important;
            font-family: '{theme["font_family"]}', monospace !important;
            white-space: pre-wrap !important;
            word-wrap: break-word !important;
            display: inline-block !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
            isolation: isolate !important;
        }}

        pre code {{
            background-color: transparent !important;
            padding: 0 !important;
            display: block !important;
            width: 100% !important;
            border: none !important;
        }}

        /* ===== MESSAGE CONTAINER STYLES ===== */
        .message-container {{
            width: 100%;
            max-width: 100%;
            white-space: pre-wrap;
            word-wrap: break-word;
            overflow-wrap: break-word;
            word-break: break-word;
            box-sizing: border-box;
            background: transparent;
        }}

        .message-reset {{
            all: initial !important;
            display: block !important;
            height: 0 !important;
            width: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            border: 0 !important;
            background: transparent !important;
        }}
        
        /* ===== MARKDOWN HEADER STYLES ===== */
        h1, h2, h3, h4, h5, h6 {{
            color: {text_color};
            margin: 0.5em 0 0.3em 0;
            font-weight: bold;
        }}

        h1 {{ font-size: 1.4em; }}
        h2 {{ font-size: 1.3em; }}
        h3 {{ font-size: 1.2em; }}
        h4 {{ font-size: 1.1em; }}
        h5 {{ font-size: 1.05em; }}
        h6 {{ font-size: 1.0em; }}        
    """

    _STYLESHEET_CACHE[theme_name] = stylesheet
    return stylesheet


def apply_theme(widget: QWidget):
    """Apply theme to a specific widget"""
    try:
        theme = THEMES[CURRENT_THEME]
        theme_with_name = dict(theme, name=CURRENT_THEME)

        stylesheet = _generate_stylesheet(theme_with_name)
        widget.setStyleSheet(stylesheet)

        font = QFont(theme["font_family"], theme["font_size"])
        widget.setFont(font)

        palette = widget.palette()
        palette.setColor(palette.ColorRole.Window, QColor(theme["background"]))
        palette.setColor(palette.ColorRole.WindowText, QColor(theme["text"]))
        palette.setColor(palette.ColorRole.Base, QColor(theme["chat_bg"]))
        palette.setColor(palette.ColorRole.Text, QColor(theme["text"]))
        palette.setColor(palette.ColorRole.Button, QColor(theme["button_bg"]))
        palette.setColor(palette.ColorRole.ButtonText, QColor(theme["text"]))
        palette.setColor(palette.ColorRole.Highlight, QColor(theme["button_hover"]))
        palette.setColor(palette.ColorRole.HighlightedText, QColor(theme["text"]))
        palette.setColor(palette.ColorRole.PlaceholderText, QColor(theme["placeholder"]))

        widget.setPalette(palette)

        logger.debug(f"Theme applied to {widget.__class__.__name__}")

    except Exception as e:
        logger.error(f"Error applying theme: {e}")


def apply_theme_to_application():
    """Apply the current theme to the entire Qt application"""
    try:
        app = QApplication.instance()
        if not app:
            return

        theme = THEMES[CURRENT_THEME]
        theme_with_name = dict(theme, name=CURRENT_THEME)

        stylesheet = _generate_stylesheet(theme_with_name)

        print(f"DEBUG: Applying theme {CURRENT_THEME} to application")
        print(f"DEBUG: Background color: {theme['background']}")
        print(f"DEBUG: Text color: {theme['text']}")

        app.setStyleSheet(stylesheet)
        app.setFont(QFont(theme["font_family"], theme["font_size"]))

        # Force refresh of ALL widgets
        widgets = app.allWidgets()
        print(f"DEBUG: Found {len(widgets)} widgets to update")
        
        for widget in widgets:
            try:
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()
            except Exception as e:
                print(f"DEBUG: Error updating widget {widget}: {e}")

        print(f"DEBUG: Theme applied to entire application: {CURRENT_THEME}")

    except Exception as e:
        print(f"DEBUG: Error applying theme: {e}")
        logger.error(f"Error applying theme to application: {e}")


__all__ = [
    'DARK_THEME',
    'LIGHT_THEME',
    'THEMES',
    'CURRENT_THEME',
    'set_theme',
    'apply_theme',
    'apply_theme_to_application'
]