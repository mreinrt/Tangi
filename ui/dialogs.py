"""
Dialog windows for Tangi
"""

import os
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QComboBox, 
    QSlider, QFileDialog, QGroupBox, QHBoxLayout, 
    QDialogButtonBox, QMessageBox, QRadioButton, QButtonGroup, 
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView, QWidget, QApplication,
    QLineEdit
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
            opacity = value / 100
            self.parent.setWindowOpacity(opacity)
            # Save to persistent settings
            self.parent.settings.setValue("window_opacity", opacity)

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
        self.setMinimumWidth(965)
        self.setMinimumHeight(1230)

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
        token_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        token_desc.setStyleSheet("color: #888888; font-style: italic; font-size: 9pt;")
        response_layout.addWidget(token_desc)

        # CREATE BUTTONS FIRST
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

        # NOW create the layout and add buttons (centered)
        preset_layout = QHBoxLayout()
        preset_layout.addStretch()
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

        # Separator (centered by default since it's full width)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        response_layout.addWidget(line)

        # Response format - centered layout
        format_label = QLabel("Response Format:")
        format_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        format_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # ← Center the label
        response_layout.addWidget(format_label)

        # Format radio buttons - centered
        format_radio_layout = QHBoxLayout()
        format_radio_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # ← Center the radio buttons
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

        format_radio_layout.addWidget(self.markdown_radio)
        format_radio_layout.addWidget(self.conversation_radio)
        response_layout.addLayout(format_radio_layout)

        format_desc = QLabel("Hover over options for details")
        format_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)  # ← Center the description
        format_desc.setStyleSheet("color: #888888; font-style: italic;")
        response_layout.addWidget(format_desc)

        response_group.setLayout(response_layout)
        layout.addWidget(response_group)

        # === NVIDIA NIM ONLINE MODE SECTION ===
        nvidia_group = QGroupBox("NVIDIA NIM Online Mode")
        nvidia_layout = QVBoxLayout()
        nvidia_layout.setSpacing(12)

        # API Base URL input (NEW)
        base_url_layout = QHBoxLayout()
        base_url_label = QLabel("API Base URL:")
        base_url_label.setMinimumWidth(60)
        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("https://integrate.api.nvidia.com/v1")
        self.base_url_input.setMinimumWidth(350)
        base_url_layout.addWidget(base_url_label)
        base_url_layout.addWidget(self.base_url_input, 1)
        nvidia_layout.addLayout(base_url_layout)

        # API Key input with show/hide toggle
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("API Key:")
        api_key_label.setMinimumWidth(60)
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("nvapi-... enter your NVIDIA API key...")
        self.api_key_input.setMinimumWidth(350)

        # Show/hide password toggle button
        self.show_key_btn = QPushButton("🌓")
        self.show_key_btn.setFixedWidth(40)
        self.show_key_btn.setToolTip("Show/hide API key")
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.clicked.connect(self.toggle_api_key_visibility)

        api_key_layout.addWidget(api_key_label)
        api_key_layout.addWidget(self.api_key_input, 1)
        api_key_layout.addWidget(self.show_key_btn)

        # Load saved API key (with proper error handling)
        nvidia_client = None
        saved_key = ""
        try:
            from Tangi.utils.online_api import OnlineAPIClient
            nvidia_client = OnlineAPIClient()
            saved_key = nvidia_client.get_api_key()
            if saved_key:
                self.api_key_input.setText(saved_key)
                logger.debug("Loaded saved NVIDIA API key")
        except ImportError as e:
            logger.error(f"Failed to import OnlineAPIClient: {e}")
        except Exception as e:
            logger.error(f"Error loading NVIDIA API key: {e}")

        # Load saved Base URL
        if nvidia_client:
            try:
                saved_base_url = nvidia_client.get_base_url()
                if saved_base_url:
                    self.base_url_input.setText(saved_base_url)
                else:
                    self.base_url_input.setText("https://integrate.api.nvidia.com/v1")
                logger.debug(f"Loaded saved Base URL: {saved_base_url}")
            except Exception as e:
                logger.error(f"Error loading Base URL: {e}")
        else:
            self.base_url_input.setText("https://integrate.api.nvidia.com/v1")

        # Status indicator for API key
        self.key_status_label = QLabel()
        self.key_status_label.setFixedWidth(20)
        self.update_key_status_indicator(bool(saved_key))

        # Add status indicator to layout
        api_key_layout.addWidget(self.key_status_label)

        nvidia_layout.addLayout(api_key_layout)

        # Test connection button with status feedback
        test_layout = QHBoxLayout()
        self.test_connection_btn = QPushButton("Test Connection")
        self.test_connection_btn.setToolTip("Test your API key with NVIDIA NIM servers")
        self.test_connection_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.test_connection_btn.clicked.connect(self.test_nvidia_connection)

        # Connection status label
        self.connection_status = QLabel("")
        self.connection_status.setStyleSheet("color: #888888; font-style: italic;")
        self.connection_status.setVisible(False)

        test_layout.addWidget(self.test_connection_btn)
        test_layout.addWidget(self.connection_status)
        test_layout.addStretch()
        nvidia_layout.addLayout(test_layout)

        # Model selection
        model_layout = QHBoxLayout()
        model_label = QLabel("Model:")
        model_label.setMinimumWidth(60)
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "mistralai/mistral-nemotron",      # Best for coding - 92.68% HumanEval
            "deepseek-ai/deepseek-v3",          # Great for code & long context
            "minimaxai/minimax-m2.5",           # Fast responses
            "nvidia/llama-3.3-nemotron-super-49b-v1",  # Powerful reasoning
            "qwen/qwen2.5-coder-32b-instruct",  # Specialized for code
            "gpt-4o-mini",                      # OpenAI fallback
            "gpt-4o"                            # OpenAI fallback
        ])
        self.model_combo.setToolTip(
            "mistralai/mistral-nemotron: Best for coding (92.68% HumanEval)\n"
            "deepseek-ai/deepseek-v3: Excellent for code generation\n"
            "minimaxai/minimax-m2.5: Fast responses\n"
            "nvidia/llama-3.3-nemotron-super-49b-v1: Powerful reasoning\n"
            "qwen/qwen2.5-coder-32b-instruct: Specialized for code"
        )

        # Model info label (dynamic)
        self.model_info_label = QLabel("")
        self.model_info_label.setStyleSheet("color: #888888; font-size: 9pt;")
        self.update_model_info_label(self.model_combo.currentText())

        # Load saved model
        if nvidia_client:
            try:
                saved_model = nvidia_client.get_model()
                idx = self.model_combo.findText(saved_model)
                if idx >= 0:
                    self.model_combo.setCurrentIndex(idx)
                    logger.debug(f"Loaded saved model: {saved_model}")
            except Exception as e:
                logger.error(f"Error loading saved model: {e}")

        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo, 1)
        model_layout.addWidget(self.model_info_label)
        model_layout.addStretch()

        nvidia_layout.addLayout(model_layout)

        # Current mode indicator (with dynamic styling)
        mode_layout = QHBoxLayout()
        mode_label = QLabel("Current Mode:")
        mode_label.setMinimumWidth(60)
        self.mode_indicator = QLabel()

        # Get current mode from parent with model info
        is_online = hasattr(parent, 'online_mode') and parent.online_mode
        model_loaded = hasattr(parent, 'llm') and parent.llm is not None

        if is_online:
            self.mode_indicator.setText("✔ Online (NVIDIA NIM)")
            self.mode_indicator.setStyleSheet("color: #00ff00; font-weight: bold; background-color: #1e3a1e; padding: 2px 8px; border-radius: 3px;")
        else:
            # Show model name if loaded
            if model_loaded and hasattr(parent, 'model_path') and parent.model_path:
                model_name = os.path.basename(parent.model_path)
                # Truncate long model names
                if len(model_name) > 35:
                    model_name = model_name[:32] + "..."
                self.mode_indicator.setText(f"✖ Offline ({model_name})")
            else:
                self.mode_indicator.setText("✖ Offline (No Model Loaded)")
            self.mode_indicator.setStyleSheet("color: #ffaa00; font-weight: bold; background-color: #3a2e1e; padding: 2px 8px; border-radius: 3px;")

        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.mode_indicator)
        mode_layout.addStretch()

        nvidia_layout.addLayout(mode_layout)

        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        nvidia_layout.addWidget(line)

        # Info label with link styling
        nvidia_info = QLabel(
            "Get your NVIDIA API key from: "
            '<a href="https://build.nvidia.com/models" style="color: #00aaff; text-decoration: none;">build.nvidia.com/models</a><br>'
            "Online mode will use NVIDIA NIM hosted API instead of local LLM.<br>"
            "Free tier: 40 requests per minute, no credit card required.<br>"
            "Compatible with OpenAI API format - works with any OpenAI-compatible endpoint."
        )
        nvidia_info.setWordWrap(True)
        nvidia_info.setOpenExternalLinks(True)
        nvidia_info.setStyleSheet("color: #888888; font-size: 9pt; padding: 5px; background-color: rgba(0,0,0,0.2); border-radius: 3px;")

        nvidia_layout.addWidget(nvidia_info)

        nvidia_group.setLayout(nvidia_layout)
        layout.addWidget(nvidia_group)

        # === DISPLAY SECTION ===
        display_group = QGroupBox("Display")
        display_layout = QVBoxLayout()
        display_layout.setSpacing(15)

        # Theme selection
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme:")
        theme_label.setMinimumWidth(60)
        self.dark_radio = QRadioButton("Dark (Green)")
        self.light_radio = QRadioButton("Light")

        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.dark_radio)
        theme_layout.addWidget(self.light_radio)
        theme_layout.addStretch()
        display_layout.addLayout(theme_layout)

        # Window transparency - with better visibility
        trans_layout = QVBoxLayout()
        trans_label = QLabel("Window Transparency:")
        trans_label.setMinimumWidth(60)
        trans_layout.addWidget(trans_label)

        # Add a horizontal layout for slider and value display
        slider_value_layout = QHBoxLayout()

        self.transparency_slider = QSlider(Qt.Orientation.Horizontal)
        self.transparency_slider.setRange(30, 100)
        self.transparency_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.transparency_slider.setTickInterval(10)

        # Load saved opacity from parent's settings
        saved_opacity = self.parent.settings.value("window_opacity", 1.0, type=float)
        self.transparency_slider.setValue(int(saved_opacity * 100))

        # Add percentage label next to slider
        self.transparency_value_label = QLabel(f"{int(saved_opacity * 100)}%")
        self.transparency_value_label.setMinimumWidth(35)
        self.transparency_value_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        slider_value_layout.addWidget(self.transparency_slider, 1)
        slider_value_layout.addWidget(self.transparency_value_label)

        trans_layout.addLayout(slider_value_layout)

        # Add a descriptive subtitle
        trans_subtitle = QLabel("Lower values = more transparent")
        trans_subtitle.setStyleSheet("color: #888888; font-size: 9pt; font-style: italic;")
        trans_layout.addWidget(trans_subtitle)

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
        
        # ===== NVIDIA SIGNAL CONNECTIONS =====
        self.base_url_input.textChanged.connect(self.save_nvidia_settings)
        self.api_key_input.textChanged.connect(self.save_nvidia_settings)
        self.model_combo.currentTextChanged.connect(self.save_nvidia_settings)
        self.model_combo.currentTextChanged.connect(self.update_model_info_label)
        
        # Update model info label initially
        self.update_model_info_label(self.model_combo.currentText())

        # Store nvidia_client for later use
        self.nvidia_client = nvidia_client

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
    
    # ==================== NVIDIA METHODS ====================
    
    def toggle_api_key_visibility(self, checked):
        """Toggle API key visibility"""
        if checked:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_key_btn.setText("🌕")
            self.show_key_btn.setToolTip("Hide API key")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_key_btn.setText("🌑")
            self.show_key_btn.setToolTip("Show API key")
    
    def update_key_status_indicator(self, has_key):
        """Update API key status indicator"""
        if has_key:
            self.key_status_label.setText("✔")
            self.key_status_label.setToolTip("API key is set")
            self.key_status_label.setStyleSheet("color: #00ff00; font-weight: bold; font-size: 14px;")
        else:
            self.key_status_label.setText("✖")
            self.key_status_label.setToolTip("No API key set")
            self.key_status_label.setStyleSheet("color: #ff4444; font-weight: bold; font-size: 14px;")
    
    def update_model_info_label(self, model_name):
        """Update model info label based on selection"""
        info_map = {
            "mistralai/mistral-nemotron": "(92.68% HumanEval - Best for coding, instruction following)",
            "deepseek-ai/deepseek-v3": "(Excellent for code generation, long context)",
            "minimaxai/minimax-m2.5": "(Fast responses, good for quick coding tasks)",
            "nvidia/llama-3.3-nemotron-super-49b-v1": "(Powerful reasoning, tool calling)",
            "qwen/qwen2.5-coder-32b-instruct": "(Specialized for code generation)",
            "gpt-4o-mini": "(Fast, efficient - OpenAI)",
            "gpt-4o": "(Best overall - OpenAI)"
        }
        self.model_info_label.setText(info_map.get(model_name, ""))
    
    def save_nvidia_settings(self):
        """Save NVIDIA NIM settings"""
        try:
            from Tangi.utils.online_api import OnlineAPIClient
            base_url = self.base_url_input.text().strip()
            api_key = self.api_key_input.text().strip()
            model = self.model_combo.currentText()
            
            client = OnlineAPIClient()
            if base_url:
                client.set_base_url(base_url)
            if api_key:
                client.set_api_key(api_key)
            client.set_model(model)
            
            # Update parent if online mode is active
            if hasattr(self.parent, 'online_mode') and self.parent.online_mode:
                if hasattr(self.parent, 'openai_client'):
                    self.parent.openai_client.set_base_url(base_url)
                    self.parent.openai_client.set_api_key(api_key)
                    self.parent.openai_client.set_model(model)
                    
            # Update status indicator
            self.update_key_status_indicator(bool(api_key))
            
        except Exception as e:
            logger.error(f"Error saving NVIDIA settings: {e}")
    
    def test_nvidia_connection(self):
        """Test NVIDIA NIM API connection"""
        try:
            from Tangi.utils.online_api import OnlineAPIClient
            
            base_url = self.base_url_input.text().strip()
            api_key = self.api_key_input.text().strip()
            
            if not api_key:
                QMessageBox.warning(self, "No API Key", "Please enter an NVIDIA API key first.")
                return
            
            if not base_url:
                base_url = "https://integrate.api.nvidia.com/v1"
            
            # Update UI
            self.test_connection_btn.setEnabled(False)
            self.test_connection_btn.setText("Testing...")
            self.connection_status.setText("Connecting to NVIDIA NIM...")
            self.connection_status.setVisible(True)
            QApplication.processEvents()
            
            client = OnlineAPIClient(api_key=api_key, base_url=base_url)
            success = client.test_connection()
            
            # Restore UI
            self.test_connection_btn.setEnabled(True)
            self.test_connection_btn.setText("Test Connection")
            
            if success:
                self.connection_status.setText("✅ Connection successful!")
                self.connection_status.setStyleSheet("color: #00ff00;")
                self.update_key_status_indicator(True)
                QMessageBox.information(self, "Success", "NVIDIA NIM API connection successful!\n\nYou can now enable Online mode.\n\nFree tier: 40 requests per minute.")
            else:
                self.connection_status.setText("❌ Connection failed")
                self.connection_status.setStyleSheet("color: #ff4444;")
                QMessageBox.warning(self, "Failed", "Connection failed. Check your API key and internet connection.")
            
            # Auto-hide status after 3 seconds
            QTimer.singleShot(3000, lambda: self.connection_status.setVisible(False))
                
        except Exception as e:
            self.test_connection_btn.setEnabled(True)
            self.test_connection_btn.setText("Test Connection")
            self.connection_status.setText(f"Error: {str(e)[:50]}")
            self.connection_status.setStyleSheet("color: #ff4444;")
            self.connection_status.setVisible(True)
            QTimer.singleShot(5000, lambda: self.connection_status.setVisible(False))
            QMessageBox.critical(self, "Error", f"Connection test failed: {str(e)}")
    
    # ==================== THEME METHODS ====================
    
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
    
    # ==================== FORMAT METHODS ====================
    
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
    
    # ==================== RAM METHODS ====================
    
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
    
    # ==================== TOKEN METHODS ====================
    
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
    
    # ==================== STORAGE METHODS ====================
    
    def select_storage(self):
        """Handle storage directory selection"""
        if self.select_storage_callback:
            self.select_storage_callback()
    
    # ==================== TRANSPARENCY METHODS ====================
    
    def live_transparency_change(self, value):
        """Handle transparency slider changes"""
        if self.parent:
            opacity = value / 100
            self.parent.setWindowOpacity(opacity)
            # Save to persistent settings
            self.parent.settings.setValue("window_opacity", opacity)
            # Update the percentage label
            if hasattr(self, 'transparency_value_label'):
                self.transparency_value_label.setText(f"{value}%")
                
    # ==================== THEME BUTTON METHODS ====================
    
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
    
    # ==================== SHOW EVENT ====================
    
    def showEvent(self, event):
        """Handle dialog show event"""
        super().showEvent(event)
        
        from Tangi.ui.theme import CURRENT_THEME
        
        # Set theme buttons directly from CURRENT_THEME
        self.dark_radio.setChecked(CURRENT_THEME == "dark")
        self.light_radio.setChecked(CURRENT_THEME == "light")
        
        # Update other UI elements
        self.update_format_buttons()
        
        # Update RAM settings
        current_ram = getattr(self.parent, 'ram_percentage', DEFAULT_RAM_PERCENTAGE)
        self.ram_slider.setValue(current_ram)
        self.on_ram_slider_changed(current_ram)
        
        # Update token settings
        current_tokens = getattr(self.parent, 'max_tokens_setting', 512)
        self.token_value_label.setText(f"Current setting: {current_tokens} tokens")
        est_time = current_tokens / 3
        self.token_time_label.setText(f"Estimated time on average CPU: ~{est_time:.0f} seconds")
        self.update_token_buttons(current_tokens)
        
        # Update mode indicator on show
        self._update_mode_indicator()
        
        # Update NVIDIA API settings
        if hasattr(self, 'nvidia_client') and self.nvidia_client:
            # Update Base URL
            current_base_url = self.nvidia_client.get_base_url()
            if current_base_url:
                self.base_url_input.setText(current_base_url)
            
            # Update API key
            current_api_key = self.nvidia_client.get_api_key()
            self.update_key_status_indicator(bool(current_api_key))
            if current_api_key:
                self.api_key_input.setText(current_api_key)
        
        # Update model selection
        if hasattr(self, 'nvidia_client') and self.nvidia_client:
            current_model = self.nvidia_client.get_model()
            idx = self.model_combo.findText(current_model)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
        
        # Sync transparency slider with current window opacity
        current_opacity = self.parent.windowOpacity()
        self.transparency_slider.setValue(int(current_opacity * 100))

    def _update_mode_indicator(self):
        """Update the mode indicator with current status"""
        # Get current mode from parent
        is_online = hasattr(self.parent, 'online_mode') and self.parent.online_mode
        model_loaded = hasattr(self.parent, 'llm') and self.parent.llm is not None
        
        if is_online:
            self.mode_indicator.setText("✔ Online (NVIDIA NIM)")
            self.mode_indicator.setStyleSheet(
                "color: #00ff00; font-weight: bold; background-color: #1e3a1e; "
                "padding: 2px 8px; border-radius: 3px;"
            )
        else:
            # Show model name if loaded
            if model_loaded and hasattr(self.parent, 'model_path') and self.parent.model_path:
                model_name = os.path.basename(self.parent.model_path)
                # Truncate long model names to prevent layout issues
                if len(model_name) > 35:
                    model_name = model_name[:32] + "..."
                self.mode_indicator.setText(f"✖ Offline ({model_name})")
            else:
                self.mode_indicator.setText("✖ Offline (No Model Loaded)")
            self.mode_indicator.setStyleSheet(
                "color: #ffaa00; font-weight: bold; background-color: #3a2e1e; "
                "padding: 2px 8px; border-radius: 3px;"
            )
            
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
        
        "Thank you to the open-source community for making this possible!"
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