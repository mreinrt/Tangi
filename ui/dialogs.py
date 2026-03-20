"""
Dialog windows for Tangi
"""

import os
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QComboBox, 
    QSlider, QFileDialog, QGroupBox, QHBoxLayout, 
    QDialogButtonBox, QMessageBox, QRadioButton, QButtonGroup, 
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView, QWidget, QApplication
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QGuiApplication, QClipboard

from Tangi.ui.theme import apply_theme, set_theme, CURRENT_THEME, THEMES, apply_theme_to_application

logger = logging.getLogger(__name__)

# RAM constants - will be overridden by main window values
SYSTEM_RAM_MB = 11161
DEFAULT_RAM_PERCENTAGE = 85


# Theme-aware file dialog wrapper
def themed_file_dialog(parent, caption, directory, filter):
    """Create a file dialog with theme applied and mounted drives in sidebar"""
    # Create dialog with DontUseNativeDialog to allow customization
    dialog = QFileDialog(parent, caption, directory, filter)
    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    
    apply_theme(dialog)
    
    if parent and hasattr(parent, 'windowOpacity'):
        dialog.setWindowOpacity(parent.windowOpacity())
    
    dialog.setModal(True)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    
    add_mounted_drives_to_sidebar(dialog)
    
    return dialog


def add_mounted_drives_to_sidebar(dialog):
    """Add mounted drives to the left sidebar of the file dialog"""
    import os
    
    sidebar_urls = []
    
    # Get list of mounted drives on Linux
    try:
        # Read /proc/mounts to find mounted filesystems
        mounts_file = '/proc/mounts' if os.path.exists('/proc/mounts') else '/etc/mtab'
        
        with open(mounts_file, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    device = parts[0]
                    mount_point = parts[1]
                    fs_type = parts[2] if len(parts) > 2 else ''
                    
                    # Filter for physical drives and common mount points
                    if (mount_point.startswith('/media/') or 
                        mount_point.startswith('/mnt/') or
                        mount_point == '/' or
                        (mount_point.startswith('/run/media/')) or
                        (device.startswith('/dev/') and 
                         not fs_type.startswith('tmpfs') and
                         not fs_type.startswith('devtmpfs') and
                         not fs_type.startswith('proc') and
                         not fs_type.startswith('sysfs') and
                         not fs_type.startswith('fusectl') and
                         not fs_type.startswith('securityfs') and
                         not fs_type.startswith('cgroup') and
                         not fs_type.startswith('pstore') and
                         not fs_type.startswith('bpf') and
                         not fs_type.startswith('configfs') and
                         not fs_type.startswith('debugfs') and
                         not fs_type.startswith('tracefs'))):
                        
                        # Check if mount point exists and is accessible
                        if os.path.exists(mount_point) and os.path.isdir(mount_point):
                            sidebar_urls.append(QUrl.fromLocalFile(mount_point))
                            
    except Exception as e:
        logger.warning(f"Could not read mounted drives: {e}")
    
    # Add home directory if not already present
    home = os.path.expanduser('~')
    home_url = QUrl.fromLocalFile(home)
    if home_url not in sidebar_urls:
        sidebar_urls.insert(0, home_url)
    
    # Remove duplicates
    seen = set()
    unique_urls = []
    for url in sidebar_urls:
        path = url.toLocalFile()
        if path not in seen:
            seen.add(path)
            unique_urls.append(url)
    
    # Set the sidebar URLs
    if unique_urls:
        dialog.setSidebarUrls(unique_urls)


class DisplayOptionsDialog(QDialog):
    """Dialog for display settings (theme, transparency)"""
    
    def __init__(self, parent=None, apply_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.apply_callback = apply_callback

        self.setWindowTitle("Display Settings")
        self.setModal(False)
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Theme group
        self.theme_group = QGroupBox("Theme")
        theme_layout = QVBoxLayout()
        
        self.theme_button_group = QButtonGroup(self)
        
        self.dark_radio = QRadioButton("Dark (Green)")
        self.theme_button_group.addButton(self.dark_radio, 0)
        theme_layout.addWidget(self.dark_radio)
        
        self.light_radio = QRadioButton("Light")
        self.theme_button_group.addButton(self.light_radio, 1)
        theme_layout.addWidget(self.light_radio)
        
        theme_layout.addStretch()
        self.theme_group.setLayout(theme_layout)
        layout.addWidget(self.theme_group)

        # Transparency group
        self.trans_group = QGroupBox("Window Transparency")
        trans_layout = QVBoxLayout()
        self.transparency_slider = QSlider(Qt.Orientation.Horizontal)
        self.transparency_slider.setRange(30, 100)
        self.transparency_slider.setValue(int(parent.windowOpacity() * 100) if parent else 100)
        trans_layout.addWidget(self.transparency_slider)
        self.trans_group.setLayout(trans_layout)
        layout.addWidget(self.trans_group)

        # Close button
        close_btn = QPushButton("Close")
        layout.addWidget(close_btn)

        # Connect signals
        self.dark_radio.toggled.connect(self.on_theme_toggled)
        self.light_radio.toggled.connect(self.on_theme_toggled)
        self.transparency_slider.valueChanged.connect(self.live_transparency_change)
        close_btn.clicked.connect(self.close)

        # Initialize
        self.update_theme_buttons()
        apply_theme(self)

    def update_theme_buttons(self):
        """Update theme buttons to match current theme"""
        try:
            self.dark_radio.toggled.disconnect(self.on_theme_toggled)
            self.light_radio.toggled.disconnect(self.on_theme_toggled)
        except:
            pass
            
        self.dark_radio.setChecked(CURRENT_THEME == "dark")
        self.light_radio.setChecked(CURRENT_THEME == "light")
        
        self.dark_radio.toggled.connect(self.on_theme_toggled)
        self.light_radio.toggled.connect(self.on_theme_toggled)

    def on_theme_toggled(self, checked):
        """Handle theme radio button toggles"""
        if not checked:
            return
            
        if self.dark_radio.isChecked():
            set_theme("dark")
        elif self.light_radio.isChecked():
            set_theme("light")
        
        apply_theme_to_application()
        
        if self.apply_callback:
            self.apply_callback()

    def live_transparency_change(self, value):
        """Handle transparency slider changes"""
        if self.parent:
            self.parent.setWindowOpacity(value / 100)

    def showEvent(self, event):
        """Handle dialog show event"""
        super().showEvent(event)
        # Set checked state directly without disconnecting signals
        self.dark_radio.setChecked(CURRENT_THEME == "dark")
        self.light_radio.setChecked(CURRENT_THEME == "light")


class PreferencesDialog(QDialog):
    """Preferences dialog for application settings"""
    
    def __init__(self, parent=None, apply_theme_callback=None, select_storage_callback=None):
        super().__init__(parent)
        self.parent = parent
        self.apply_theme_callback = apply_theme_callback
        self.select_storage_callback = select_storage_callback
        self._changing_theme = False  # Prevent recursive theme changes

        # Get RAM values from parent if available
        global SYSTEM_RAM_MB, DEFAULT_RAM_PERCENTAGE
        if hasattr(parent, 'ram_percentage'):
            DEFAULT_RAM_PERCENTAGE = parent.ram_percentage
        
        self.setWindowTitle("Preferences")
        self.setModal(False)
        self.setMinimumWidth(500)
        self.setMinimumHeight(650)

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # === STORAGE SECTION ===
        storage_group = QGroupBox("Storage")
        storage_layout = QVBoxLayout()
        
        storage_dir_layout = QHBoxLayout()
        storage_dir_label = QLabel("Chat History Location:")
        storage_path_label = QLabel(
            self.parent.default_storage_dir if hasattr(self.parent, 'default_storage_dir') 
            else "~/.Tangi"
        )
        storage_path_label.setWordWrap(True)
        storage_dir_layout.addWidget(storage_dir_label)
        storage_dir_layout.addWidget(storage_path_label, 1)
        
        storage_btn_layout = QHBoxLayout()
        storage_btn = QPushButton("Change Storage Directory")
        storage_btn.clicked.connect(self.select_storage)
        storage_btn_layout.addWidget(storage_btn)
        storage_btn_layout.addStretch()
        
        storage_layout.addLayout(storage_dir_layout)
        storage_layout.addLayout(storage_btn_layout)
        storage_group.setLayout(storage_layout)
        layout.addWidget(storage_group)

        # === PERFORMANCE SECTION ===
        performance_group = QGroupBox("Performance")
        performance_layout = QVBoxLayout()
        performance_layout.setSpacing(15)
        
        # RAM Allocation
        ram_label = QLabel("RAM Allocation for Models:")
        performance_layout.addWidget(ram_label)
        
        self.ram_slider = QSlider(Qt.Orientation.Horizontal)
        self.ram_slider.setRange(50, 95)
        current_ram = getattr(parent, 'ram_percentage', DEFAULT_RAM_PERCENTAGE)
        self.ram_slider.setValue(current_ram)
        performance_layout.addWidget(self.ram_slider)
        
        system_gb = SYSTEM_RAM_MB / 1024
        gb_value = (SYSTEM_RAM_MB * current_ram / 100) / 1024
        
        # Create RAM label without hardcoded colors - will be set by update method
        self.ram_value_label = QLabel()
        self.ram_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ram_value_label.setStyleSheet("background-color: transparent;")
        performance_layout.addWidget(self.ram_value_label)
        
        ram_desc = QLabel("Higher = More context capacity (may use swap if needed)")
        ram_desc.setStyleSheet("color: #888888; font-style: italic; font-size: 9pt;")
        performance_layout.addWidget(ram_desc)
        
        performance_group.setLayout(performance_layout)
        layout.addWidget(performance_group)

        # === RESPONSE SETTINGS SECTION ===
        response_group = QGroupBox("Response Settings")
        response_layout = QVBoxLayout()
        response_layout.setSpacing(15)

        # Token limit description
        token_desc = QLabel(
            "Maximum tokens per response. Higher = longer responses but slower.\n"
            "• 512: Very simple code (one-liners, tiny functions)\n"
            "• 1024: Simple code (small functions, basic scripts)\n"
            "• 2048: Medium code (calculators, classes)\n"
            "• 4096: Complex code (full programs, libraries)"
        )
        token_desc.setWordWrap(True)
        token_desc.setStyleSheet("color: #888888; font-style: italic; font-size: 9pt;")
        response_layout.addWidget(token_desc)

        # Token preset buttons
        preset_layout = QHBoxLayout()
        self.token_512_btn = QPushButton("512 (Very Simple)")
        self.token_1024_btn = QPushButton("1024 (Simple)")
        self.token_2048_btn = QPushButton("2048 (Medium)")
        self.token_4096_btn = QPushButton("4096 (Complex)")

        # Get current token setting
        current_tokens = getattr(parent, 'max_tokens_setting', 2048)

        # Connect buttons
        for btn, val in [(self.token_512_btn, 512), (self.token_1024_btn, 1024), 
                        (self.token_2048_btn, 2048), (self.token_4096_btn, 4096)]:
            btn.clicked.connect(lambda checked, v=val: self.set_token_limit(v))

        preset_layout.addWidget(self.token_512_btn)
        preset_layout.addWidget(self.token_1024_btn)
        preset_layout.addWidget(self.token_2048_btn)
        preset_layout.addWidget(self.token_4096_btn)
        preset_layout.addStretch()
        response_layout.addLayout(preset_layout)

        # Current token display
        self.token_value_label = QLabel(f"Current setting: {current_tokens} tokens")
        self.token_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.token_value_label.setStyleSheet("font-weight: bold; font-size: 11pt; margin-top: 10px;")
        response_layout.addWidget(self.token_value_label)

        # Estimated time note
        est_time = current_tokens / 3
        self.token_time_label = QLabel(f"Estimated time on average CPU: ~{est_time:.0f} seconds")
        self.token_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.token_time_label.setStyleSheet("color: #888888; font-style: italic;")
        response_layout.addWidget(self.token_time_label)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        response_layout.addWidget(line)

        # Response format
        format_label = QLabel("Response Format:")
        format_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        response_layout.addWidget(format_label)
        
        self.markdown_radio = QRadioButton("Markdown Mode")
        self.markdown_radio.setToolTip(
            "Formats responses with rich Markdown:\n"
            "- Code blocks with syntax highlighting\n"
            "- Headers, lists, tables\n"
            "- Bold, italic, links\n"
            "- Best for technical content"
        )
        
        self.conversation_radio = QRadioButton("Conversation Mode")
        self.conversation_radio.setToolTip(
            "Simple, clean conversation view:\n"
            "- Text appears next to role prefix\n"
            "- Line breaks preserved\n"
            "- Basic formatting (bold, italic)\n"
            "- Best for natural conversation"
        )
        
        self.format_button_group = QButtonGroup(self)
        self.format_button_group.addButton(self.markdown_radio, 0)
        self.format_button_group.addButton(self.conversation_radio, 1)
        
        response_layout.addWidget(self.markdown_radio)
        response_layout.addWidget(self.conversation_radio)
        
        format_desc = QLabel("Hover over options for details")
        format_desc.setStyleSheet("color: #888888; font-style: italic;")
        response_layout.addWidget(format_desc)
        
        response_group.setLayout(response_layout)
        layout.addWidget(response_group)

        # === DISPLAY SECTION ===
        display_group = QGroupBox("Display")
        display_layout = QVBoxLayout()
        display_layout.setSpacing(15)
        
        # Theme selection
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme:")
        self.dark_radio = QRadioButton("Dark (Green)")
        self.light_radio = QRadioButton("Light")
        
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.dark_radio)
        theme_layout.addWidget(self.light_radio)
        theme_layout.addStretch()
        display_layout.addLayout(theme_layout)
        
        # Window transparency
        trans_layout = QVBoxLayout()
        trans_label = QLabel("Window Transparency:")
        trans_layout.addWidget(trans_label)
        
        self.transparency_slider = QSlider(Qt.Orientation.Horizontal)
        self.transparency_slider.setRange(30, 100)
        self.transparency_slider.setValue(int(self.parent.windowOpacity() * 100) if parent else 100)
        trans_layout.addWidget(self.transparency_slider)
        display_layout.addLayout(trans_layout)
        
        display_group.setLayout(display_layout)
        layout.addWidget(display_group)

        # Connect signals
        self.dark_radio.toggled.connect(self.on_theme_toggled)
        self.light_radio.toggled.connect(self.on_theme_toggled)
        self.markdown_radio.toggled.connect(self.on_format_toggled)
        self.conversation_radio.toggled.connect(self.on_format_toggled)
        self.ram_slider.valueChanged.connect(self.on_ram_slider_changed)
        self.transparency_slider.valueChanged.connect(self.live_transparency_change)

        layout.addStretch()

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)
        close_btn.clicked.connect(self.close)

        # Initialize button states
        self.update_theme_buttons()
        self.update_format_buttons()
        self.update_token_buttons(current_tokens)
        
        # Set initial RAM label text
        self.on_ram_slider_changed(current_ram)
        
        apply_theme(self)
        self.adjustSize()

    def on_theme_toggled(self, checked):
        """Handle theme radio button toggles"""
        if not checked:
            return
        
        # Prevent recursive theme changes
        if self._changing_theme:
            return
        
        self._changing_theme = True
        
        try:
            # Get which button was clicked
            if self.dark_radio.isChecked():
                new_theme = "dark"
            elif self.light_radio.isChecked():
                new_theme = "light"
            else:
                return
            
            # Only change if different from current
            from Tangi.ui.theme import CURRENT_THEME, set_theme, apply_theme_to_application
            if new_theme == CURRENT_THEME:
                return
            
            # Set the theme
            set_theme(new_theme)
            apply_theme_to_application()
            
            # Force this dialog to refresh
            apply_theme(self)
            self.repaint()
            
            # Call the main window's refresh method if it exists
            if hasattr(self.parent, 'refresh_theme'):
                self.parent.refresh_theme()
            
            if self.apply_theme_callback:
                self.apply_theme_callback()
                
        finally:
            self._changing_theme = False

    def refresh_theme(self):
        """Refresh dialog theme when application theme changes"""
        from Tangi.ui.theme import CURRENT_THEME, apply_theme
        
        # Re-apply theme to this dialog
        apply_theme(self)
        
        # Update button states to match new theme
        self.dark_radio.setChecked(CURRENT_THEME == "dark")
        self.light_radio.setChecked(CURRENT_THEME == "light")
        
        # Update RAM label color based on new theme
        current_value = self.ram_slider.value()
        self.on_ram_slider_changed(current_value)
        
        # Update any other theme-dependent UI elements
        self.update_format_buttons()
        
        # Update token button highlight with new theme color
        current_tokens = getattr(self.parent, 'max_tokens_setting', 512)
        self.update_token_buttons(current_tokens)
        
        # Force a repaint
        self.repaint()

    def on_format_toggled(self, checked):
        """Handle format radio button toggles"""
        if not checked:
            return
            
        if self.markdown_radio.isChecked():
            new_format = "markdown"
        elif self.conversation_radio.isChecked():
            new_format = "conversation"
        else:
            return
        
        if hasattr(self.parent, 'set_response_format'):
            self.parent.set_response_format(new_format)
            logger.info(f"Response format changed to: {new_format}")

    def on_ram_slider_changed(self, value):
        """Handle RAM slider changes"""
        try:
            import psutil
            mem = psutil.virtual_memory()
            available_gb = mem.available / (1024**3)
            total_gb = mem.total / (1024**3)
            available_percent = (mem.available / mem.total) * 100
            
            warning = ""
            if available_percent < 20:
                warning = f" ⚠️ Low available RAM: {available_gb:.1f}GB"
            elif available_percent < 40:
                warning = f" ⚠️ Moderate available RAM: {available_gb:.1f}GB"
            
            # Update the label text
            self.ram_value_label.setText(
                f"{value}% of total ({value/100*total_gb:.1f}GB) | "
                f"Available: {available_gb:.1f}GB ({available_percent:.0f}%){warning}"
            )
            
            # Apply theme-appropriate color - use normal text color, not colored warnings
            from Tangi.ui.theme import CURRENT_THEME
            if CURRENT_THEME == "dark":
                self.ram_value_label.setStyleSheet("color: #00ff00; background-color: transparent;")
            else:
                self.ram_value_label.setStyleSheet("color: #000000; background-color: transparent;")
            
            # Store in parent
            if hasattr(self.parent, 'set_ram_percentage'):
                self.parent.set_ram_percentage(value)
                
        except Exception as e:
            logger.error(f"Error updating RAM slider: {e}")

    def live_transparency_change(self, value):
        """Handle transparency slider changes"""
        if self.parent:
            self.parent.setWindowOpacity(value / 100)

    def update_theme_buttons(self):
        """Update theme buttons to match current theme"""
        from Tangi.ui.theme import CURRENT_THEME
        
        try:
            self.dark_radio.toggled.disconnect(self.on_theme_toggled)
            self.light_radio.toggled.disconnect(self.on_theme_toggled)
        except:
            pass
        
        self.dark_radio.setChecked(CURRENT_THEME == "dark")
        self.light_radio.setChecked(CURRENT_THEME == "light")
        
        self.dark_radio.toggled.connect(self.on_theme_toggled)
        self.light_radio.toggled.connect(self.on_theme_toggled)

    def update_format_buttons(self):
        """Update format buttons to match current format"""
        if hasattr(self.parent, 'response_format'):
            current_format = self.parent.response_format
        else:
            current_format = "markdown"
        
        try:
            self.markdown_radio.toggled.disconnect(self.on_format_toggled)
            self.conversation_radio.toggled.disconnect(self.on_format_toggled)
        except:
            pass
        
        self.markdown_radio.setChecked(current_format == "markdown")
        self.conversation_radio.setChecked(current_format == "conversation")
        
        self.markdown_radio.toggled.connect(self.on_format_toggled)
        self.conversation_radio.toggled.connect(self.on_format_toggled)

    def update_token_buttons(self, current_tokens):
        """Highlight the active token button"""
        from Tangi.ui.theme import CURRENT_THEME
        
        highlight_color = "#555555" if CURRENT_THEME == "dark" else "#cccccc"
        
        # Reset all button styles first
        for btn in [self.token_512_btn, self.token_1024_btn, self.token_2048_btn, self.token_4096_btn]:
            btn.setStyleSheet("")
        
        # Highlight the active one
        for btn, val in [(self.token_512_btn, 512), (self.token_1024_btn, 1024), 
                        (self.token_2048_btn, 2048), (self.token_4096_btn, 4096)]:
            if val == current_tokens:
                btn.setStyleSheet(f"font-weight: bold; background-color: {highlight_color};")
                break

    def set_token_limit(self, value):
        """Handle token preset button clicks"""
        # Update the display
        self.token_value_label.setText(f"Current setting: {value} tokens")
        
        # Update time estimate
        est_time = value / 3
        self.token_time_label.setText(f"Estimated time on average CPU: ~{est_time:.0f} seconds")
        
        # Store in parent
        if hasattr(self.parent, 'set_max_tokens'):
            self.parent.set_max_tokens(value)
        
        # Update button highlighting LIVE
        self.update_token_buttons(value)
        
        logger.info(f"Token limit set to: {value}")

    def select_storage(self):
        """Handle storage directory selection"""
        if self.select_storage_callback:
            self.select_storage_callback()
            
    def showEvent(self, event):
        """Handle dialog show event"""
        super().showEvent(event)
        
        from Tangi.ui.theme import CURRENT_THEME
        
        # Set theme buttons directly from CURRENT_THEME
        self.dark_radio.setChecked(CURRENT_THEME == "dark")
        self.light_radio.setChecked(CURRENT_THEME == "light")
        
        # Update other UI elements
        self.update_format_buttons()
        
        current_ram = getattr(self.parent, 'ram_percentage', DEFAULT_RAM_PERCENTAGE)
        self.ram_slider.setValue(current_ram)
        self.on_ram_slider_changed(current_ram)
        
        current_tokens = getattr(self.parent, 'max_tokens_setting', 512)
        self.token_value_label.setText(f"Current setting: {current_tokens} tokens")
        est_time = current_tokens / 3
        self.token_time_label.setText(f"Estimated time on average CPU: ~{est_time:.0f} seconds")
        self.update_token_buttons(current_tokens)

class AboutDialog(QDialog):
    """About dialog with donation information"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("About Tangi")
        self.setModal(True)
        self.setMinimumWidth(550)
        self.setMinimumHeight(350)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        label = QLabel(
        "Tangi was created by Mike (BigSlimThic), a self-taught developer from Philadelphia who has faced extraordinary challenges. "
        "Growing up on the tough streets of Philly and later struggling to survive with no stable residency since 18, "
        "he's experienced homelessness, unstable housing, and countless days wondering where the next meal would come from. "
        "Now based in the Philippines, he continues to face daily hardships—living without running water and electricity, "
        "and the constant uncertainty that comes with unstable residency.<br><br>"
        
        "Despite these circumstances, Mike taught himself Linux—specifically Gentoo—and software engineering from the ground up. "
        "Every line of code in Tangi was written on hardware most would consider obsolete, against odds that would have stopped most people. "
        "But what keeps him going is his girlfriend, who works as a kasambahay (stay-in domestic helper) for an abusive boss. "
        "She endures long hours and mistreatment, all while dreaming of a better life for herself and her family. "
        "Her strength reminds Mike every day why he can't give up. The streets of Philadelphia taught him resilience; "
        "Gentoo taught him that you can build something powerful from the ground up if you're willing to put in the work.<br><br>"
        
        "Tangi exists because Mike refuses to let his circumstances define his future—and because he dreams of a day when his girlfriend "
        "no longer has to work for someone who mistreats her, when her family has enough, and when they can finally build a life together "
        "with dignity and stability. It's proof that where you come from doesn't determine where you're going.<br><br>"
        
        "This project is dedicated to everyone who has ever been told they can't, shouldn't, or won't make it—the underdogs, "
        "the overlooked, the ones grinding in the dark when no one's watching. It's for the kasambahay working through abuse, "
        "for the families who go without, and for anyone fighting for something better. If a guy from Philly with no running water "
        "can build this, imagine what you can do.<br><br>"
        
        "If you find value in Tangi, consider supporting its creator. Your support helps Mike continue developing and improving "
        "this tool, and moves him—and the woman who inspires him—closer to basic necessities many take for granted: "
        "stable electricity, running water, reliable internet, freedom from abuse, and a place to finally call home together.<br><br>"
        
        "Thank you DeepSeek for when those times got hard!"
    )
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        # BTC donation
        btc_layout = QHBoxLayout()
        btc_label = QLabel("BTC:")
        btc_label.setFixedWidth(40)
        btc_address = QLabel("3GtCgHhMP7NTxsdNjcDs7TUNSBK6EXoAzz")
        btc_address.setWordWrap(True)
        
        self.btc_copy_btn = QPushButton("Copy")
        self.btc_copy_btn.setFixedWidth(80)
        self.btc_copy_btn.clicked.connect(lambda: self.copy_to_clipboard_with_flash(
            "3GtCgHhMP7NTxsdNjcDs7TUNSBK6EXoAzz", "BTC", self.btc_copy_btn))
        
        btc_layout.addWidget(btc_label)
        btc_layout.addWidget(btc_address)
        btc_layout.addWidget(self.btc_copy_btn)
        layout.addLayout(btc_layout)

        # ETH donation
        eth_layout = QHBoxLayout()
        eth_label = QLabel("ETH:")
        eth_label.setFixedWidth(40)
        eth_address = QLabel("0x5f1ed610a96c648478a775644c9244bf4e78631e")
        eth_address.setWordWrap(True)
        
        self.eth_copy_btn = QPushButton("Copy")
        self.eth_copy_btn.setFixedWidth(80)
        self.eth_copy_btn.clicked.connect(lambda: self.copy_to_clipboard_with_flash(
            "0x5f1ed610a96c648478a775644c9244bf4e78631e", "ETH", self.eth_copy_btn))
        
        eth_layout.addWidget(eth_label)
        eth_layout.addWidget(eth_address)
        eth_layout.addWidget(self.eth_copy_btn)
        layout.addLayout(eth_layout)

        layout.addStretch()

        btn = QPushButton("Close")
        btn.setFixedWidth(100)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)

        apply_theme(self)

    def copy_to_clipboard_with_flash(self, address, coin_type, button):
        """Copy address to clipboard and flash button"""
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(address)
        
        original_text = button.text()
        original_style = button.styleSheet()
        
        button.setText("Copied!")
        
        if CURRENT_THEME == "dark":
            button.setStyleSheet(f"""
                QPushButton {{
                    background-color: #333333;
                    color: #00ff00;
                    border: 1px solid #00ff00;
                    padding: 5px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: #444444;
                }}
            """)
        else:
            button.setStyleSheet(f"""
                QPushButton {{
                    background-color: #333333;
                    color: #ffffff;
                    border: 1px solid #000000;
                    padding: 5px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: #444444;
                }}
            """)
        
        button.setEnabled(False)
        
        QTimer.singleShot(300, lambda: self.revert_button(button, original_text, original_style))

    def revert_button(self, button, original_text, original_style):
        """Revert button after flash"""
        button.setText(original_text)
        button.setStyleSheet(original_style)
        button.setEnabled(True)


__all__ = [
    'themed_file_dialog',
    'add_mounted_drives_to_sidebar',
    'DisplayOptionsDialog',
    'PreferencesDialog',
    'AboutDialog'
]