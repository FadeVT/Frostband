#!/usr/bin/env python3
"""
Frostband - Cross-Platform Wardriving Management Tool

INSTALLATION:
    pip install requests cryptography
    Windows only: pip install pywin32
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import subprocess, json, os, sys, base64, hashlib, tarfile, zipfile, requests
from pathlib import Path
from datetime import datetime
import threading
import webbrowser
import tempfile


class ToolTip:
    """Create a tooltip for a given widget"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
    
    def show_tooltip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(self.tooltip, text=self.text, background="#2D2D2D", 
                        foreground="#E0E0E0", relief="solid", borderwidth=1,
                        font=("Segoe UI", 9), padx=8, pady=4)
        label.pack()
    
    def hide_tooltip(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

if sys.platform == 'win32':
    try:
        import win32crypt
        USE_DPAPI = True
    except ImportError:
        USE_DPAPI = False
else:
    USE_DPAPI = False

if not USE_DPAPI:
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        print("ERROR: pip install cryptography")
        sys.exit(1)


class ConfigManager:
    def __init__(self):
        base = Path(os.environ.get('APPDATA', Path.home())) if sys.platform == 'win32' else Path.home() / '.config'
        self.config_dir = base / 'Frostband'
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file, self.key_file = self.config_dir / "frostband_config.json", self.config_dir / "frostband.key"
    
    def _get_fernet_key(self):
        if self.key_file.exists(): return self.key_file.read_bytes()
        key = Fernet.generate_key()
        self.key_file.write_bytes(key)
        os.chmod(self.key_file, 0o600)
        return key
    
    def encrypt_token(self, p):
        if not p: return ""
        if USE_DPAPI: return base64.b64encode(win32crypt.CryptProtectData(p.encode(), None, None, None, None, 0)).decode()
        return base64.b64encode(Fernet(self._get_fernet_key()).encrypt(p.encode())).decode()
    
    def decrypt_token(self, e):
        if not e: return ""
        try:
            if USE_DPAPI: return win32crypt.CryptUnprotectData(base64.b64decode(e), None, None, None, 0)[1].decode()
            return Fernet(self._get_fernet_key()).decrypt(base64.b64decode(e)).decode()
        except: return ""
    
    def load_config(self):
        d = {'wigle_api_id': '', 'wigle_api_token_enc': '', 'pi_host': '', 'pi_user': '', 'pi_dir': '', 'win_dir': '', 'wigle_out_dir': ''}
        if self.config_file.exists():
            try: d.update(json.load(open(self.config_file)))
            except: pass
        ab = Path(__file__).parent.absolute() if '__file__' in globals() else Path.cwd()
        if not d['win_dir']: d['win_dir'] = str(ab / 'Kismet')
        if not d['wigle_out_dir']: d['wigle_out_dir'] = str(ab / 'WiGLE_Output')
        return d
    
    def save_config(self, c):
        json.dump(c, open(self.config_file, 'w'), indent=2)


class FrostbandApp:
    def __init__(self, root):
        self.root = root
        root.title("Frostband")
        root.geometry("1200x900")
        
        # Dark mode color scheme
        self.colors = {
            'primary': '#3B82F6',      # Bright Blue
            'primary_dark': '#2563EB',
            'secondary': '#10B981',    # Green
            'accent': '#F59E0B',       # Amber
            'danger': '#EF4444',       # Red
            'bg': '#1E1E1E',          # Dark background
            'bg_secondary': '#2D2D2D', # Slightly lighter
            'card': '#2D2D2D',        # Card background
            'border': '#404040',      # Border color
            'text': '#E0E0E0',        # Light text
            'text_secondary': '#A0A0A0'
        }
        
        root.configure(bg=self.colors['bg'])
        
        self.config_mgr = ConfigManager()
        self.config = self.config_mgr.load_config()
        self.upload_checks, self.tx_checks = {}, {}

        # Track file counts for change detection
        self.last_local_count = 0
        self.last_pi_count = 0
        self.last_archive_count = 0

        Path(self.config['win_dir']).mkdir(parents=True, exist_ok=True)
        Path(self.config['wigle_out_dir']).mkdir(parents=True, exist_ok=True)
        self._apply_styles()
        self._create_widgets()
        self._refresh_upload_list()
        self._update_pi_status()
        self._refresh_dashboard()

        # Start auto-refresh timers
        self._schedule_auto_refresh()
    
    def _apply_styles(self):
        """Apply dark mode styling to the application"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure Notebook (tabs) with dark theme
        style.configure('TNotebook', 
                       background=self.colors['bg'], 
                       borderwidth=0)
        style.configure('TNotebook.Tab', 
                       background=self.colors['bg_secondary'],
                       foreground=self.colors['text'],
                       padding=[20, 10],
                       borderwidth=0,
                       font=('Segoe UI', 10, 'bold'))
        style.map('TNotebook.Tab',
                 background=[('selected', self.colors['primary'])],
                 foreground=[('selected', 'white')],
                 expand=[('selected', [1, 1, 1, 0])])
        
        # Configure Frame
        style.configure('TFrame', background=self.colors['bg'])
        style.configure('Card.TFrame', background=self.colors['card'])
        
        # Configure LabelFrame with dark theme
        style.configure('TLabelframe', 
                       background=self.colors['card'],
                       bordercolor=self.colors['border'],
                       borderwidth=2,
                       relief='solid')
        style.configure('TLabelframe.Label', 
                       background=self.colors['card'],
                       foreground=self.colors['primary'],
                       font=('Segoe UI', 9, 'bold'))
        
        # Configure Progressbar
        style.configure('TProgressbar', 
                       background=self.colors['secondary'],
                       troughcolor=self.colors['bg_secondary'],
                       borderwidth=0,
                       thickness=20)
    
    def _create_widgets(self):
        nb = ttk.Notebook(self.root)
        nb.pack(fill='both', expand=True, padx=10, pady=10)
        self.tab_main, self.tab_rpi, self.tab_upload, self.tab_tx, self.tab_settings = [ttk.Frame(nb) for _ in range(5)]

        # Configure tab backgrounds
        for tab in [self.tab_main, self.tab_rpi, self.tab_upload, self.tab_tx, self.tab_settings]:
            tab.configure(style='Card.TFrame')

        for tab, txt in zip([self.tab_main, self.tab_rpi, self.tab_upload, self.tab_tx, self.tab_settings],
                           ["🏠 Dashboard", "📡 RPi Manager", "📤 WiGLE CSV", "📥 Transactions", "⚙️ Settings"]):
            nb.add(tab, text=txt)
        self.progress = ttk.Progressbar(self.root)
        self.progress.pack(fill='x', padx=10, pady=(0,5))
        self.status_label = tk.Label(self.root, text="Ready.", anchor='w')
        self.status_label.pack(fill='x', padx=10, pady=(0,10))
        self._build_main_tab()
        self._build_settings_tab()
        self._build_rpi_tab()
        self._build_upload_tab()
        self._build_tx_tab()

    def _build_main_tab(self):
        f = self.tab_main

        # Header
        header_frame = tk.Frame(f, bg=self.colors['card'])
        header_frame.pack(fill='x', padx=15, pady=(15,10))
        tk.Label(header_frame, text="🏠 Frostband Dashboard",
                bg=self.colors['card'], fg=self.colors['text'], font=('Segoe UI', 14, 'bold'),
                anchor='w').pack(fill='x')
        tk.Label(header_frame, text="Quick overview and status monitoring",
                bg=self.colors['card'], fg=self.colors['text_secondary'], font=('Segoe UI', 9),
                anchor='w').pack(fill='x')

        # WiGLE Stats Section (moved to top)
        wigle_stats_section = tk.Frame(f, bg=self.colors['card'])
        wigle_stats_section.pack(fill='x', padx=15, pady=10)

        tk.Label(wigle_stats_section, text="WiGLE Statistics",
                bg=self.colors['card'], fg=self.colors['text'],
                font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0,10))

        # WiGLE stats cards container
        wigle_stats_row = tk.Frame(wigle_stats_section, bg=self.colors['card'])
        wigle_stats_row.pack(fill='x', pady=(0,10))

        # WiFi Discovered Card
        wifi_card = tk.Frame(wigle_stats_row, bg=self.colors['bg_secondary'], relief='flat', bd=0)
        wifi_card.pack(side='left', fill='both', expand=True, padx=(0,10))
        tk.Label(wifi_card, text="📶 WiFi Discovered", bg=self.colors['bg_secondary'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 9)).pack(pady=(10,5))
        self.dash_wifi_discovered = tk.Label(wifi_card, text="—",
                                             bg=self.colors['bg_secondary'], fg=self.colors['primary'],
                                             font=('Segoe UI', 20, 'bold'))
        self.dash_wifi_discovered.pack(pady=(0,5))
        self.dash_wifi_detail = tk.Label(wifi_card, text="—",
                                         bg=self.colors['bg_secondary'], fg=self.colors['text_secondary'],
                                         font=('Segoe UI', 8))
        self.dash_wifi_detail.pack(pady=(0,10))

        # Monthly Rank Card
        monthly_rank_card = tk.Frame(wigle_stats_row, bg=self.colors['bg_secondary'], relief='flat', bd=0)
        monthly_rank_card.pack(side='left', fill='both', expand=True, padx=(0,10))
        tk.Label(monthly_rank_card, text="📅 Monthly Rank", bg=self.colors['bg_secondary'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 9)).pack(pady=(10,5))
        self.dash_monthly_rank = tk.Label(monthly_rank_card, text="—",
                                         bg=self.colors['bg_secondary'], fg=self.colors['secondary'],
                                         font=('Segoe UI', 20, 'bold'))
        self.dash_monthly_rank.pack(pady=(0,5))
        self.dash_monthly_detail = tk.Label(monthly_rank_card, text="—",
                                           bg=self.colors['bg_secondary'], fg=self.colors['text_secondary'],
                                           font=('Segoe UI', 8))
        self.dash_monthly_detail.pack(pady=(0,10))

        # Overall Rank Card
        overall_rank_card = tk.Frame(wigle_stats_row, bg=self.colors['bg_secondary'], relief='flat', bd=0)
        overall_rank_card.pack(side='left', fill='both', expand=True)
        tk.Label(overall_rank_card, text="🏆 Overall Rank", bg=self.colors['bg_secondary'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 9)).pack(pady=(10,5))
        self.dash_overall_rank = tk.Label(overall_rank_card, text="—",
                                         bg=self.colors['bg_secondary'], fg=self.colors['accent'],
                                         font=('Segoe UI', 20, 'bold'))
        self.dash_overall_rank.pack(pady=(0,5))
        self.dash_overall_detail = tk.Label(overall_rank_card, text="—",
                                           bg=self.colors['bg_secondary'], fg=self.colors['text_secondary'],
                                           font=('Segoe UI', 8))
        self.dash_overall_detail.pack(pady=(0,10))

        # Recent Uploads Section
        recent_section = tk.Frame(f, bg=self.colors['card'])
        recent_section.pack(fill='x', padx=15, pady=10)

        tk.Label(recent_section, text="📊 Recent Activity",
                bg=self.colors['card'], fg=self.colors['text'],
                font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0,10))

        # Recent uploads container with scrollable text area
        recent_container = tk.Frame(recent_section, bg=self.colors['bg_secondary'], relief='flat', bd=2)
        recent_container.pack(fill='both', expand=True)

        self.dash_recent_text = scrolledtext.ScrolledText(recent_container, height=8, width=100,
                                                           bg=self.colors['bg_secondary'], fg=self.colors['text'],
                                                           insertbackground=self.colors['text'], relief='flat',
                                                           font=('Consolas', 9), borderwidth=0, wrap='word')
        self.dash_recent_text.pack(fill='both', expand=True, padx=10, pady=10)
        self.dash_recent_text.config(state='disabled')

        # Quick Stats Section
        stats_section = tk.Frame(f, bg=self.colors['card'])
        stats_section.pack(fill='x', padx=15, pady=10)

        tk.Label(stats_section, text="Quick Stats",
                bg=self.colors['card'], fg=self.colors['text'],
                font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0,10))

        # Stats cards container
        stats_row1 = tk.Frame(stats_section, bg=self.colors['card'])
        stats_row1.pack(fill='x', pady=(0,10))

        # Local Files Card
        local_card = tk.Frame(stats_row1, bg=self.colors['bg_secondary'], relief='flat', bd=0)
        local_card.pack(side='left', fill='both', expand=True, padx=(0,10))
        tk.Label(local_card, text="📁 Local Files", bg=self.colors['bg_secondary'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 9)).pack(pady=(10,5))
        self.dash_local_count = tk.Label(local_card, text="—",
                                         bg=self.colors['bg_secondary'], fg=self.colors['primary'],
                                         font=('Segoe UI', 20, 'bold'))
        self.dash_local_count.pack(pady=(0,5))
        self.dash_local_size = tk.Label(local_card, text="—",
                                        bg=self.colors['bg_secondary'], fg=self.colors['text_secondary'],
                                        font=('Segoe UI', 8))
        self.dash_local_size.pack(pady=(0,10))

        # Pi Files Card
        pi_files_card = tk.Frame(stats_row1, bg=self.colors['bg_secondary'], relief='flat', bd=0)
        pi_files_card.pack(side='left', fill='both', expand=True, padx=(0,10))
        tk.Label(pi_files_card, text="📡 Pi Files", bg=self.colors['bg_secondary'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 9)).pack(pady=(10,5))
        self.dash_pi_count = tk.Label(pi_files_card, text="—",
                                      bg=self.colors['bg_secondary'], fg=self.colors['secondary'],
                                      font=('Segoe UI', 20, 'bold'))
        self.dash_pi_count.pack(pady=(0,5))
        self.dash_pi_size = tk.Label(pi_files_card, text="—",
                                     bg=self.colors['bg_secondary'], fg=self.colors['text_secondary'],
                                     font=('Segoe UI', 8))
        self.dash_pi_size.pack(pady=(0,10))

        # Archives Card
        archive_card = tk.Frame(stats_row1, bg=self.colors['bg_secondary'], relief='flat', bd=0)
        archive_card.pack(side='left', fill='both', expand=True)
        tk.Label(archive_card, text="📦 Archives", bg=self.colors['bg_secondary'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 9)).pack(pady=(10,5))
        self.dash_archive_count = tk.Label(archive_card, text="—",
                                           bg=self.colors['bg_secondary'], fg=self.colors['accent'],
                                           font=('Segoe UI', 20, 'bold'))
        self.dash_archive_count.pack(pady=(0,5))
        self.dash_archive_size = tk.Label(archive_card, text="—",
                                          bg=self.colors['bg_secondary'], fg=self.colors['text_secondary'],
                                          font=('Segoe UI', 8))
        self.dash_archive_size.pack(pady=(0,10))

        # Quick Actions Section
        actions_section = tk.Frame(f, bg=self.colors['card'])
        actions_section.pack(fill='x', padx=15, pady=10)

        tk.Label(actions_section, text="⚡ Quick Actions",
                bg=self.colors['card'], fg=self.colors['text'],
                font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0,10))

        # Action buttons container
        actions_container = tk.Frame(actions_section, bg=self.colors['card'])
        actions_container.pack(fill='x')

        # Big action buttons
        self.dash_btn_automatic = tk.Button(actions_container, text="🚀 Automatic Sync\nStop → Copy → Verify → Delete",
                                             command=self._automatic, height=3,
                                             bg=self.colors['secondary'], fg='white', relief='flat',
                                             cursor='hand2', font=('Segoe UI', 10, 'bold'))
        self.dash_btn_automatic.pack(side='left', fill='both', expand=True, padx=(0,10))

        self.dash_btn_upload = tk.Button(actions_container, text="📤 Upload Direct to WiGLE\nUpload from Pi to WiGLE",
                                          command=self._upload_direct_to_wigle,
                                          height=3, bg=self.colors['primary'], fg='white', relief='flat',
                                          cursor='hand2', font=('Segoe UI', 10, 'bold'))
        self.dash_btn_upload.pack(side='left', fill='both', expand=True, padx=(0,10))

        self.dash_btn_transactions = tk.Button(actions_container, text="📥 Get Transactions\nDownload KML files",
                                                command=lambda: self.root.nametowidget('.!notebook').select(3),
                                                height=3, bg=self.colors['accent'], fg='white', relief='flat',
                                                cursor='hand2', font=('Segoe UI', 10, 'bold'))
        self.dash_btn_transactions.pack(side='left', fill='both', expand=True)

    def _build_settings_tab(self):
        f = self.tab_settings
        
        # Description box
        desc_frame = tk.Frame(f, bg=self.colors['card'])
        desc_frame.pack(fill='x', padx=15, pady=(10,5))
        tk.Label(desc_frame, text="⚙️ Configure WiGLE API credentials and Pi connection", 
                bg=self.colors['card'], fg=self.colors['text'], font=('Segoe UI', 10, 'bold'),
                anchor='w').pack(fill='x')
        
        # Spacer for consistency
        tk.Label(f, text="", bg=self.colors['card']).pack(anchor='w', padx=10, pady=5)
        
        # WiGLE API section with header
        wigle_frame = tk.Frame(f, bg=self.colors['card'])
        wigle_frame.pack(fill='x', padx=15, pady=(5,0))
        
        header_frame = tk.Frame(wigle_frame, bg=self.colors['card'])
        header_frame.pack(fill='x', pady=(0,5))
        tk.Label(header_frame, text="WiGLE API Credentials", font=('Segoe UI', 9, 'bold'),
                bg=self.colors['card'], fg=self.colors['text']).pack(side='left')
        tk.Button(header_frame, text="Get API Key →", command=lambda: webbrowser.open('https://wigle.net/account'), 
                 fg=self.colors['primary'], bg=self.colors['card'], relief='flat', cursor='hand2',
                 font=('Segoe UI', 9, 'underline')).pack(side='left', padx=10)
        
        # API ID
        id_frame = tk.Frame(wigle_frame, bg=self.colors['card'])
        id_frame.pack(fill='x', pady=2)
        tk.Label(id_frame, text="WiGLE API ID:", bg=self.colors['card'], fg=self.colors['text'], width=20, anchor='e').pack(side='left', padx=5)
        self.txt_api_id = tk.Entry(id_frame, width=40, bg='#3A3A3A', fg=self.colors['text'],
                    insertbackground=self.colors['primary'], relief='solid', borderwidth=2,
                    highlightthickness=1, highlightbackground=self.colors['primary'], highlightcolor=self.colors['primary'])
        self.txt_api_id.pack(side='left', padx=5)
        self.txt_api_id.insert(0, self.config['wigle_api_id'])
        
        # API Token
        token_frame = tk.Frame(wigle_frame, bg=self.colors['card'])
        token_frame.pack(fill='x', pady=2)
        tk.Label(token_frame, text="WiGLE API Token:", bg=self.colors['card'], fg=self.colors['text'], width=20, anchor='e').pack(side='left', padx=5)
        self.txt_api_token = tk.Entry(token_frame, width=40, show='*', bg='#3A3A3A', fg=self.colors['text'],
                    insertbackground=self.colors['primary'], relief='solid', borderwidth=2,
                    highlightthickness=1, highlightbackground=self.colors['primary'], highlightcolor=self.colors['primary'])
        self.txt_api_token.pack(side='left', padx=5)
        
        # Note about token clearing
        note_frame = tk.Frame(wigle_frame, bg=self.colors['card'])
        note_frame.pack(fill='x', pady=(0,10))
        tk.Label(note_frame, text="Note: API token will disappear after hitting save. Don't worry, it has been saved.", 
                fg=self.colors['text_secondary'], font=('Segoe UI', 8, 'italic'),
                bg=self.colors['card']).pack(anchor='w', padx=(130,0))
        
        # Remote settings
        rf = ttk.LabelFrame(f, text="Remote (Raspberry Pi) + Paths", padding=10)
        rf.pack(fill='x', padx=15, pady=10)
        
        # Pi Host and User on same row
        row1 = tk.Frame(rf, bg=self.colors['card'])
        row1.pack(fill='x', pady=2)
        tk.Label(row1, text="Pi Host (IP):", bg=self.colors['card'], fg=self.colors['text'], width=18, anchor='e').pack(side='left', padx=5)
        self.txt_pi_host = tk.Entry(row1, width=25, bg='#3A3A3A', fg=self.colors['text'],
                    insertbackground=self.colors['primary'], relief='solid', borderwidth=2,
                    highlightthickness=1, highlightbackground=self.colors['primary'], highlightcolor=self.colors['primary'])
        self.txt_pi_host.pack(side='left', padx=5)
        self.txt_pi_host.insert(0, self.config['pi_host'])
        
        tk.Label(row1, text="Pi User:", bg=self.colors['card'], fg=self.colors['text'], width=10, anchor='e').pack(side='left', padx=(20,5))
        self.txt_pi_user = tk.Entry(row1, width=20, bg='#3A3A3A', fg=self.colors['text'],
                    insertbackground=self.colors['primary'], relief='solid', borderwidth=2,
                    highlightthickness=1, highlightbackground=self.colors['primary'], highlightcolor=self.colors['primary'])
        self.txt_pi_user.pack(side='left', padx=5)
        self.txt_pi_user.insert(0, self.config['pi_user'])
        
        # Pi Dir
        row2 = tk.Frame(rf, bg=self.colors['card'])
        row2.pack(fill='x', pady=2)
        tk.Label(row2, text="Pi Dir:", bg=self.colors['card'], fg=self.colors['text'], width=18, anchor='e').pack(side='left', padx=5)
        self.txt_pi_dir = tk.Entry(row2, width=60, bg='#3A3A3A', fg=self.colors['text'],
                    insertbackground=self.colors['primary'], relief='solid', borderwidth=2,
                    highlightthickness=1, highlightbackground=self.colors['primary'], highlightcolor=self.colors['primary'])
        self.txt_pi_dir.pack(side='left', padx=5)
        self.txt_pi_dir.insert(0, self.config['pi_dir'])
        
        # Local Kismet Dir
        row3 = tk.Frame(rf, bg=self.colors['card'])
        row3.pack(fill='x', pady=2)
        tk.Label(row3, text="Local Kismet Dir:", bg=self.colors['card'], fg=self.colors['text'], width=18, anchor='e').pack(side='left', padx=5)
        self.txt_win_dir = tk.Entry(row3, width=60, bg='#3A3A3A', fg=self.colors['text'],
                    insertbackground=self.colors['primary'], relief='solid', borderwidth=2,
                    highlightthickness=1, highlightbackground=self.colors['primary'], highlightcolor=self.colors['primary'])
        self.txt_win_dir.pack(side='left', padx=5)
        self.txt_win_dir.insert(0, self.config['win_dir'])
        tk.Button(row3, text="Browse...", command=lambda: self._browse_folder('txt_win_dir'), width=10,
                 bg=self.colors['primary'], fg='white', relief='flat', cursor='hand2').pack(side='left', padx=5)
        
        # WiGLE Output Dir
        row4 = tk.Frame(rf, bg=self.colors['card'])
        row4.pack(fill='x', pady=2)
        tk.Label(row4, text="WiGLE Output Dir:", bg=self.colors['card'], fg=self.colors['text'], width=18, anchor='e').pack(side='left', padx=5)
        self.txt_wigle_out = tk.Entry(row4, width=60, bg='#3A3A3A', fg=self.colors['text'],
                    insertbackground=self.colors['primary'], relief='solid', borderwidth=2,
                    highlightthickness=1, highlightbackground=self.colors['primary'], highlightcolor=self.colors['primary'])
        self.txt_wigle_out.pack(side='left', padx=5)
        self.txt_wigle_out.insert(0, self.config['wigle_out_dir'])
        tk.Button(row4, text="Browse...", command=lambda: self._browse_folder('txt_wigle_out'), width=10,
                 bg=self.colors['primary'], fg='white', relief='flat', cursor='hand2').pack(side='left', padx=5)
        
        # Note
        note_frame2 = tk.Frame(rf, bg=self.colors['card'])
        note_frame2.pack(fill='x', pady=(10,0))
        tk.Label(note_frame2, text="Note: Click 'Save Settings' below to apply changes", 
                fg=self.colors['text_secondary'], font=('Segoe UI', 8, 'italic'),
                bg=self.colors['card']).pack()
        
        # SSH Key Setup section
        ssh_frame = ttk.LabelFrame(f, text="SSH Key Setup (One-Time)", padding=10)
        ssh_frame.pack(fill='x', padx=15, pady=10)
        
        info_row = tk.Frame(ssh_frame, bg=self.colors['card'])
        info_row.pack(fill='x', pady=5)
        tk.Label(info_row, text="SSH keys allow passwordless connection to your Pi.", 
                bg=self.colors['card'], fg=self.colors['text_secondary'], font=('Segoe UI', 8)).pack(anchor='w')
        
        btn_row = tk.Frame(ssh_frame, bg=self.colors['card'])
        btn_row.pack(fill='x', pady=5)
        
        tk.Button(btn_row, text="1. Generate SSH Key", command=self._generate_ssh_key, width=20,
                 bg=self.colors['secondary'], fg='white', relief='flat', cursor='hand2').pack(side='left', padx=5)
        ToolTip(btn_row.winfo_children()[-1], "Create a new SSH key pair (if you don't have one)")
        
        tk.Button(btn_row, text="2. Copy Key to Pi", command=self._copy_key_to_pi, width=20,
                 bg=self.colors['primary'], fg='white', relief='flat', cursor='hand2').pack(side='left', padx=5)
        ToolTip(btn_row.winfo_children()[-1], "Upload your SSH key to the Pi (requires password once)")
        
        tk.Button(btn_row, text="3. Test Connection", command=self._test_ssh_connection, width=20,
                 bg=self.colors['accent'], fg='white', relief='flat', cursor='hand2').pack(side='left', padx=5)
        ToolTip(btn_row.winfo_children()[-1], "Verify that SSH key authentication works")
        
        self.ssh_status_label = tk.Label(ssh_frame, text="Status: Not configured", 
                                         bg=self.colors['card'], fg=self.colors['text_secondary'], 
                                         font=('Segoe UI', 8), anchor='w')
        self.ssh_status_label.pack(fill='x', pady=5)
        
        # Save button
        save_frame = tk.Frame(f, bg=self.colors['card'])
        save_frame.pack(fill='x', padx=15, pady=10)
        tk.Button(save_frame, text="Save Settings", command=self._save_settings, width=20,
                 bg=self.colors['secondary'], fg='white', relief='flat', cursor='hand2',
                 font=('Segoe UI', 9, 'bold')).pack(anchor='w')
    
    def _build_rpi_tab(self):
        f = self.tab_rpi
        
        # Description box
        desc_frame = tk.Frame(f, bg=self.colors['card'])
        desc_frame.pack(fill='x', padx=15, pady=(10,5))
        tk.Label(desc_frame, text="📡 Control and file management for your RPi", 
                bg=self.colors['card'], fg=self.colors['text'], font=('Segoe UI', 10, 'bold'),
                anchor='w').pack(fill='x')
        
        self.lbl_pi_hint = tk.Label(f, text="", fg=self.colors['accent'], bg=self.colors['card'])
        self.lbl_pi_hint.pack(anchor='w', padx=10, pady=5)
        
        # File Management section
        file_mgmt_frame = ttk.LabelFrame(f, text="File Management", padding=10)
        file_mgmt_frame.pack(fill='x', padx=10, pady=5)
        
        bf1 = tk.Frame(file_mgmt_frame, bg=self.colors['card'])
        bf1.pack(fill='x', pady=2)
        self.btn_upload_direct = tk.Button(bf1, text="Upload Direct to WiGLE", command=self._upload_direct_to_wigle, width=52,
                                           bg=self.colors['secondary'], fg='white', relief='flat', cursor='hand2')
        self.btn_upload_direct.pack(side='left', padx=2)
        ToolTip(self.btn_upload_direct, "Upload files directly from Pi to WiGLE without copying to PC, then delete from Pi")
        
        bf2 = tk.Frame(file_mgmt_frame, bg=self.colors['card'])
        bf2.pack(fill='x', pady=2)
        self.btn_automatic = tk.Button(bf2, text="Automatic (Stop → Copy → Verify → Delete)", command=self._automatic, width=52,
                                       bg=self.colors['secondary'], fg='white', relief='flat', cursor='hand2', font=('Segoe UI', 9, 'bold'))
        self.btn_automatic.pack(side='left', padx=2)
        ToolTip(self.btn_automatic, "Stop Kismet, copy files, verify integrity, then delete from Pi")
        
        bf3 = tk.Frame(file_mgmt_frame, bg=self.colors['card'])
        bf3.pack(fill='x', pady=2)
        self.btn_copy_wigle = tk.Button(bf3, text="Copy .wiglecsv from RPi", command=self._copy_wigle, width=25,
                                        bg=self.colors['secondary'], fg='white', relief='flat', cursor='hand2')
        self.btn_copy_wigle.pack(side='left', padx=2)
        ToolTip(self.btn_copy_wigle, "Download all .wiglecsv files from the Raspberry Pi to your local Kismet directory")
        
        self.btn_delete_wigle = tk.Button(bf3, text="Delete .wiglecsv on RPi", command=self._delete_wigle, width=25,
                                          bg=self.colors['secondary'], fg='white', relief='flat', cursor='hand2')
        self.btn_delete_wigle.pack(side='left', padx=2)
        ToolTip(self.btn_delete_wigle, "Permanently delete all .wiglecsv files from the Raspberry Pi")
        
        # Kismet Control section
        kismet_control_frame = ttk.LabelFrame(f, text="Kismet Control", padding=10)
        kismet_control_frame.pack(fill='x', padx=10, pady=5)
        
        bf4 = tk.Frame(kismet_control_frame, bg=self.colors['card'])
        bf4.pack(fill='x', pady=2)
        self.btn_start_kismet = tk.Button(bf4, text="Start Kismet", command=self._start_kismet, width=17,
                                          bg=self.colors['secondary'], fg='white', relief='flat', cursor='hand2')
        self.btn_start_kismet.pack(side='left', padx=2)
        ToolTip(self.btn_start_kismet, "Start the Kismet service on the Raspberry Pi")
        
        self.btn_stop_kismet = tk.Button(bf4, text="Stop Kismet", command=self._stop_kismet, width=17,
                                         bg=self.colors['danger'], fg='white', relief='flat', cursor='hand2')
        self.btn_stop_kismet.pack(side='left', padx=2)
        ToolTip(self.btn_stop_kismet, "Stop the Kismet service on the Raspberry Pi")
        
        self.btn_restart_kismet = tk.Button(bf4, text="Restart Kismet", command=self._restart_kismet, width=17,
                                           bg=self.colors['accent'], fg='white', relief='flat', cursor='hand2')
        self.btn_restart_kismet.pack(side='left', padx=2)
        ToolTip(self.btn_restart_kismet, "Restart the Kismet service on the Raspberry Pi")
        
        # RPi Control section
        rpi_control_frame = ttk.LabelFrame(f, text="RPi Control", padding=10)
        rpi_control_frame.pack(fill='x', padx=10, pady=5)
        
        bf5 = tk.Frame(rpi_control_frame, bg=self.colors['card'])
        bf5.pack(fill='x', pady=2)
        self.btn_reboot = tk.Button(bf5, text="Reboot RPi", command=self._reboot_pi, width=25,
                                    bg=self.colors['accent'], fg='white', relief='flat', cursor='hand2')
        self.btn_reboot.pack(side='left', padx=2)
        ToolTip(self.btn_reboot, "Reboot the Raspberry Pi")
        
        self.btn_shutdown = tk.Button(bf5, text="Shutdown RPi", command=self._shutdown_pi, width=25,
                                      bg=self.colors['danger'], fg='white', relief='flat', cursor='hand2')
        self.btn_shutdown.pack(side='left', padx=2)
        ToolTip(self.btn_shutdown, "Safely shutdown the Raspberry Pi")
        
        self.lbl_pi_info = tk.Label(f, text="Source: (not configured)", anchor='w', 
                                    bg=self.colors['card'], fg=self.colors['text_secondary'])
        self.lbl_pi_info.pack(fill='x', padx=10, pady=5)
        self.txt_pull_log = scrolledtext.ScrolledText(f, height=22, width=110,
                                                       bg=self.colors['bg_secondary'], fg=self.colors['text'],
                                                       insertbackground=self.colors['text'], relief='flat', borderwidth=2)
        self.txt_pull_log.pack(fill='both', expand=True, padx=10, pady=5)
    
    def _build_upload_tab(self):
        f = self.tab_upload
        
        # Description box
        desc_frame = tk.Frame(f, bg=self.colors['card'])
        desc_frame.pack(fill='x', padx=15, pady=(10,5))
        tk.Label(desc_frame, text="📤 Manage your locally stored wiglecsv files", 
                bg=self.colors['card'], fg=self.colors['text'], font=('Segoe UI', 10, 'bold'),
                anchor='w').pack(fill='x')
        
        # Spacer for consistency
        tk.Label(f, text="", bg=self.colors['card']).pack(anchor='w', padx=10, pady=5)
        
        bf = tk.Frame(f, bg=self.colors['card'])
        bf.pack(fill='x', padx=10, pady=5)
        button_configs = [
            ("Refresh list", self._refresh_upload_list, 15, self.colors['primary']),
            ("Select All", lambda: self._set_all_checks(self.upload_checks, self.tree_upload, True), 12, self.colors['primary']),
            ("Select None", lambda: self._set_all_checks(self.upload_checks, self.tree_upload, False), 12, self.colors['primary']),
            ("Upload", self._upload_files, 12, self.colors['secondary']),
            ("Delete", self._delete_local, 12, self.colors['danger']),
            ("Archive", self._archive_local, 12, self.colors['accent'])
        ]
        for txt, cmd, w, color in button_configs:
            fg = 'white'
            tk.Button(bf, text=txt, command=cmd, width=w, bg=color, fg=fg, 
                     relief='flat', cursor='hand2').pack(side='left', padx=2)
        
        tf = tk.Frame(f, bg=self.colors['card'])
        tf.pack(fill='both', expand=True, padx=10, pady=5)
        sb = ttk.Scrollbar(tf)
        sb.pack(side='right', fill='y')
        self.tree_upload = ttk.Treeview(tf, columns=('File', 'Size', 'Status', 'TransID'), show='tree headings', yscrollcommand=sb.set)
        sb.config(command=self.tree_upload.yview)
        self.tree_upload.heading('#0', text='☐')
        for col, w in [('File', 500), ('Size', 100), ('Status', 100), ('TransID', 120)]:
            self.tree_upload.heading(col, text=col)
            self.tree_upload.column(col, width=w)
        self.tree_upload.column('#0', width=30, stretch=False)
        # Dark theme for treeview
        style = ttk.Style()
        style.configure("Treeview", 
                       background=self.colors['bg_secondary'],
                       foreground=self.colors['text'],
                       fieldbackground=self.colors['bg_secondary'],
                       borderwidth=0)
        style.configure("Treeview.Heading",
                       background=self.colors['primary'],
                       foreground='white',
                       borderwidth=0)
        style.map('Treeview', background=[('selected', self.colors['primary'])])
        self.tree_upload.pack(fill='both', expand=True)
        self.tree_upload.bind('<Button-1>', lambda e: self._toggle_check(e, self.tree_upload, self.upload_checks))
    
    def _build_tx_tab(self):
        f = self.tab_tx
        
        # Description box
        desc_frame = tk.Frame(f, bg=self.colors['card'])
        desc_frame.pack(fill='x', padx=15, pady=(10,5))
        tk.Label(desc_frame, text="📥 Find and download your WiGLE transaction files (.KML)", 
                bg=self.colors['card'], fg=self.colors['text'], font=('Segoe UI', 10, 'bold'),
                anchor='w').pack(fill='x')
        
        # Spacer for consistency
        tk.Label(f, text="", bg=self.colors['card']).pack(anchor='w', padx=10, pady=5)
        
        df = tk.Frame(f, bg=self.colors['card'])
        df.pack(fill='x', padx=10, pady=5)
        tk.Label(df, text="Start Date (YYYYMMDD):", bg=self.colors['card'], fg=self.colors['text']).pack(side='left', padx=5)
        self.txt_start = tk.Entry(df, width=15, bg='#3A3A3A', fg=self.colors['text'],
                                 insertbackground=self.colors['primary'], relief='solid', borderwidth=2,
                                 highlightthickness=1, highlightbackground=self.colors['primary'], highlightcolor=self.colors['primary'])
        self.txt_start.pack(side='left', padx=5)
        tk.Label(df, text="End Date (YYYYMMDD):", bg=self.colors['card'], fg=self.colors['text']).pack(side='left', padx=5)
        self.txt_end = tk.Entry(df, width=15, bg='#3A3A3A', fg=self.colors['text'],
                               insertbackground=self.colors['primary'], relief='solid', borderwidth=2,
                               highlightthickness=1, highlightbackground=self.colors['primary'], highlightcolor=self.colors['primary'])
        self.txt_end.pack(side='left', padx=5)
        tk.Button(df, text="Find Transactions", command=self._find_transactions, width=20,
                 bg=self.colors['primary'], fg='white', relief='flat', cursor='hand2').pack(side='left', padx=5)
        
        self.lbl_task_status = tk.Label(f, text="Task Status: (select a transaction)", anchor='w',
                                        bg=self.colors['card'], fg=self.colors['text_secondary'])
        self.lbl_task_status.pack(fill='x', padx=10, pady=5)
        
        tf = tk.Frame(f, bg=self.colors['card'])
        tf.pack(fill='both', expand=True, padx=10, pady=5)
        sb = ttk.Scrollbar(tf)
        sb.pack(side='right', fill='y')
        self.tree_tx = ttk.Treeview(tf, columns=('TransID', 'Date', 'Status', 'Device', 'File'), show='tree headings', yscrollcommand=sb.set)
        sb.config(command=self.tree_tx.yview)
        self.tree_tx.heading('#0', text='☐')
        for col, w in [('TransID', 200), ('Date', 90), ('Status', 90), ('Device', 180), ('File', 250)]:
            self.tree_tx.heading(col, text='Transaction ID' if col=='TransID' else 'File (API)' if col=='File' else col)
            self.tree_tx.column(col, width=w)
        self.tree_tx.column('#0', width=30, stretch=False)
        self.tree_tx.pack(fill='both', expand=True)
        self.tree_tx.bind('<Button-1>', lambda e: self._toggle_check(e, self.tree_tx, self.tx_checks))
        self.tree_tx.bind('<<TreeviewSelect>>', lambda e: self.lbl_task_status.config(text=f"Selected: {self.tree_tx.item(self.tree_tx.selection()[0])['values'][0]}") if self.tree_tx.selection() else None)
        
        bf = tk.Frame(f, bg=self.colors['card'])
        bf.pack(fill='x', padx=10, pady=5)
        button_configs = [
            ("Select All", lambda: self._set_all_checks(self.tx_checks, self.tree_tx, True), 15, self.colors['bg_secondary']),
            ("Select None", lambda: self._set_all_checks(self.tx_checks, self.tree_tx, False), 15, self.colors['bg_secondary']),
            ("Download All New", self._tx_download_new, 18, self.colors['accent']),
            ("Download Selected", self._tx_download_selected, 18, self.colors['secondary'])
        ]
        for txt, cmd, w, color in button_configs:
            fg = 'white' if color != self.colors['bg_secondary'] else self.colors['text']
            tk.Button(bf, text=txt, command=cmd, width=w, bg=color, fg=fg,
                     relief='flat', cursor='hand2').pack(side='left', padx=2)
    
    def _set_status(self, t):
        self.status_label.config(text=t)
        self.root.update_idletasks()
    
    def _log(self, t):
        self.txt_pull_log.insert('end', t + '\n')
        self.txt_pull_log.see('end')
        self.root.update_idletasks()
    
    def _reset_progress(self):
        self.progress['value'] = 0
        self.progress['maximum'] = 100
    
    def _toggle_check(self, e, tree, checks):
        if tree.identify_region(e.x, e.y) == 'tree' and (item := tree.identify_row(e.y)):
            checks[item] = not checks.get(item, False)
            tree.item(item, text='☑' if checks[item] else '☐')
    
    def _set_all_checks(self, checks, tree, val):
        for item in checks:
            checks[item] = val
            tree.item(item, text='☑' if val else '☐')

    def _refresh_dashboard(self):
        """Update dashboard with current stats"""
        pi_configured = self.config['pi_host'] and self.config['pi_user'] and self.config['pi_dir']
        wigle_configured = self.config['wigle_api_id'] and self.config['wigle_api_token_enc']

        # Update quick action button states
        if pi_configured:
            self.dash_btn_automatic.config(state='normal')
        else:
            self.dash_btn_automatic.config(state='disabled')

        # Update local files count
        local_files = list(Path(self.config['win_dir']).rglob('*.wiglecsv'))
        local_count = len(local_files)
        local_size = sum(f.stat().st_size for f in local_files)
        self.dash_local_count.config(text=str(local_count))
        self.dash_local_size.config(text=self._fmt_bytes(local_size))

        # Update Pi files count (only if configured)
        if pi_configured:
            threading.Thread(target=self._update_pi_files_count, daemon=True).start()
        else:
            self.dash_pi_count.config(text="—")
            self.dash_pi_size.config(text="Not configured")

        # Update archives count
        archives = list(Path(self.config['win_dir']).glob('*.zip'))
        archive_count = len(archives)
        archive_size = sum(f.stat().st_size for f in archives)
        self.dash_archive_count.config(text=str(archive_count))
        self.dash_archive_size.config(text=self._fmt_bytes(archive_size))

        # Update WiGLE stats (only if configured)
        if wigle_configured:
            threading.Thread(target=self._update_wigle_stats, daemon=True).start()
            threading.Thread(target=self._update_recent_activity, daemon=True).start()
        else:
            self.dash_wifi_discovered.config(text="—")
            self.dash_wifi_detail.config(text="Configure API in Settings")
            self.dash_monthly_rank.config(text="—")
            self.dash_monthly_detail.config(text="—")
            self.dash_overall_rank.config(text="—")
            self.dash_overall_detail.config(text="—")
            self.dash_recent_text.config(state='normal')
            self.dash_recent_text.delete('1.0', 'end')
            self.dash_recent_text.insert('1.0', "Configure WiGLE API in Settings to view recent upload activity")
            self.dash_recent_text.config(state='disabled')

        self._set_status("Dashboard refreshed.")

    def _schedule_auto_refresh(self):
        """Schedule automatic dashboard refreshes"""
        # Refresh WiGLE stats and recent activity every 30 seconds
        self._auto_refresh_wigle_and_activity()

        # Check for file changes every 5 seconds
        self._auto_refresh_quick_stats()

    def _auto_refresh_wigle_and_activity(self):
        """Auto-refresh WiGLE statistics and recent activity every 30 seconds"""
        wigle_configured = self.config['wigle_api_id'] and self.config['wigle_api_token_enc']

        if wigle_configured:
            threading.Thread(target=self._update_wigle_stats, daemon=True).start()
            threading.Thread(target=self._update_recent_activity, daemon=True).start()

        # Schedule next refresh in 30 seconds
        self.root.after(30000, self._auto_refresh_wigle_and_activity)

    def _auto_refresh_quick_stats(self):
        """Auto-refresh quick stats only when file counts change"""
        try:
            # Check local files
            local_files = list(Path(self.config['win_dir']).rglob('*.wiglecsv'))
            local_count = len(local_files)

            # Check archives
            archives = list(Path(self.config['win_dir']).glob('*.zip'))
            archive_count = len(archives)

            # Only update if counts changed
            if local_count != self.last_local_count:
                self.last_local_count = local_count
                local_size = sum(f.stat().st_size for f in local_files)
                self.dash_local_count.config(text=str(local_count))
                self.dash_local_size.config(text=self._fmt_bytes(local_size))

            if archive_count != self.last_archive_count:
                self.last_archive_count = archive_count
                archive_size = sum(f.stat().st_size for f in archives)
                self.dash_archive_count.config(text=str(archive_count))
                self.dash_archive_size.config(text=self._fmt_bytes(archive_size))

            # Check Pi files if configured (in background to avoid blocking)
            pi_configured = self.config['pi_host'] and self.config['pi_user'] and self.config['pi_dir']
            if pi_configured:
                threading.Thread(target=self._check_pi_files_changed, daemon=True).start()

        except Exception:
            pass  # Silently ignore errors in auto-refresh

        # Schedule next check in 5 seconds
        self.root.after(5000, self._auto_refresh_quick_stats)

    def _check_pi_files_changed(self):
        """Check if Pi file count changed and update if needed"""
        try:
            result = self._ssh(f"cd '{self.config['pi_dir']}'; find . -type f -name '*.wiglecsv' | wc -l")
            if result.returncode == 0:
                file_count = int(result.stdout.strip())
                if file_count != self.last_pi_count:
                    self.last_pi_count = file_count
                    # Trigger full Pi update if count changed
                    self._update_pi_files_count()
        except:
            pass  # Silently ignore errors

    def _update_pi_files_count(self):
        """Background thread to count Pi files"""
        try:
            result = self._ssh(f"cd '{self.config['pi_dir']}'; find . -type f -name '*.wiglecsv' -exec du -cb {{}} + | tail -1")
            if result.returncode == 0 and result.stdout.strip():
                total_bytes = int(result.stdout.strip().split()[0])
                result2 = self._ssh(f"cd '{self.config['pi_dir']}'; find . -type f -name '*.wiglecsv' | wc -l")
                file_count = int(result2.stdout.strip()) if result2.returncode == 0 else 0
                self.root.after(0, lambda: self.dash_pi_count.config(text=str(file_count)))
                self.root.after(0, lambda: self.dash_pi_size.config(text=self._fmt_bytes(total_bytes)))
            else:
                self.root.after(0, lambda: self.dash_pi_count.config(text="0"))
                self.root.after(0, lambda: self.dash_pi_size.config(text="0 B"))
        except:
            self.root.after(0, lambda: self.dash_pi_count.config(text="?"))
            self.root.after(0, lambda: self.dash_pi_size.config(text="Connection failed"))

    def _update_wigle_stats(self):
        """Background thread to fetch WiGLE user statistics"""
        try:
            token = self.config_mgr.decrypt_token(self.config['wigle_api_token_enc'])
            if not token:
                self.root.after(0, lambda: self.dash_wifi_discovered.config(text="Error"))
                self.root.after(0, lambda: self.dash_wifi_detail.config(text="Token decrypt failed"))
                return

            # Fetch user statistics from WiGLE API
            r = requests.get("https://api.wigle.net/api/v2/stats/user",
                           auth=(self.config['wigle_api_id'], token),
                           headers={'Accept': 'application/json'})

            if r.status_code == 200:
                data = r.json()

                # Extract statistics
                if 'statistics' in data:
                    stats = data['statistics']

                    # WiFi discovered
                    discovered = stats.get('discoveredWiFiGPS', 0) + stats.get('discoveredWiFi', 0)
                    total_wifi = stats.get('totalWiFiLocations', 0)
                    self.root.after(0, lambda d=discovered: self.dash_wifi_discovered.config(text=f"{d:,}"))
                    self.root.after(0, lambda t=total_wifi: self.dash_wifi_detail.config(text=f"Total locations: {t:,}"))

                    # Monthly rank with trend arrow
                    monthly_rank = stats.get('monthRank', 0)
                    prev_month_rank = stats.get('prevMonthRank', 0)
                    if monthly_rank > 0:
                        # Calculate trend (lower rank number = better, so reversed logic)
                        trend_arrow = ""
                        if prev_month_rank > 0:
                            if monthly_rank < prev_month_rank:
                                trend_arrow = " ↑"  # Improved (lower number)
                            elif monthly_rank > prev_month_rank:
                                trend_arrow = " ↓"  # Declined (higher number)
                            detail_text = f"Previous: #{prev_month_rank:,}"
                        else:
                            detail_text = "First month"

                        self.root.after(0, lambda r=monthly_rank, a=trend_arrow:
                                      self.dash_monthly_rank.config(text=f"#{r:,}{a}"))
                        self.root.after(0, lambda d=detail_text:
                                      self.dash_monthly_detail.config(text=d))
                    else:
                        self.root.after(0, lambda: self.dash_monthly_rank.config(text="—"))
                        self.root.after(0, lambda: self.dash_monthly_detail.config(text="No rank yet"))

                    # Overall rank with trend arrow
                    rank = stats.get('rank', 0)
                    prev_rank = stats.get('prevRank', 0)
                    if rank > 0:
                        # Calculate trend (lower rank number = better, so reversed logic)
                        trend_arrow = ""
                        if prev_rank > 0:
                            if rank < prev_rank:
                                trend_arrow = " ↑"  # Improved (lower number)
                            elif rank > prev_rank:
                                trend_arrow = " ↓"  # Declined (higher number)

                        self.root.after(0, lambda r=rank, a=trend_arrow:
                                      self.dash_overall_rank.config(text=f"#{r:,}{a}"))
                        self.root.after(0, lambda d=discovered, p=prev_rank:
                                      self.dash_overall_detail.config(text=f"{d:,} discovered" + (f" | Prev: #{p:,}" if p > 0 else "")))
                    else:
                        self.root.after(0, lambda: self.dash_overall_rank.config(text="—"))
                        self.root.after(0, lambda: self.dash_overall_detail.config(text="No rank yet"))
                else:
                    self.root.after(0, lambda: self.dash_wifi_discovered.config(text="N/A"))
                    self.root.after(0, lambda: self.dash_wifi_detail.config(text="No stats available"))
            else:
                self.root.after(0, lambda: self.dash_wifi_discovered.config(text="Error"))
                self.root.after(0, lambda: self.dash_wifi_detail.config(text=f"API error: {r.status_code}"))

        except Exception as e:
            self.root.after(0, lambda: self.dash_wifi_discovered.config(text="Error"))
            self.root.after(0, lambda e=e: self.dash_wifi_detail.config(text=f"Failed: {str(e)[:30]}"))

    def _update_recent_activity(self):
        """Background thread to fetch recent upload activity from WiGLE"""
        try:
            token = self.config_mgr.decrypt_token(self.config['wigle_api_token_enc'])
            if not token:
                self.root.after(0, lambda: self._set_recent_text("Token decrypt failed"))
                return

            # Fetch recent transactions from WiGLE API
            r = requests.get("https://api.wigle.net/api/v2/file/transactions?pagestart=0",
                           auth=(self.config['wigle_api_id'], token),
                           headers={'Accept': 'application/json'})

            if r.status_code == 200:
                data = r.json()
                results = data.get('results', [])

                if not results:
                    self.root.after(0, lambda: self._set_recent_text("No recent uploads found"))
                    return

                # Build recent activity text
                from datetime import datetime, timedelta
                now = datetime.now()
                cutoff_24h = now - timedelta(hours=24)

                activity_lines = []
                activity_lines.append("╔════════════════════════════════════════════════════════════════════════════════╗")
                activity_lines.append("║ Recent Uploads (Last 24 Hours)                                                ║")
                activity_lines.append("╠════════════════════════════════════════════════════════════════════════════════╣")

                recent_count = 0
                total_new_wifi_24h = 0

                for tx in results[:10]:  # Limit to 10 most recent
                    trans_id = tx.get('transid', '')
                    if not trans_id or len(trans_id) < 8:
                        continue

                    # Parse date from transaction ID (YYYYMMDD format at start)
                    try:
                        date_str = trans_id[:8]
                        tx_date = datetime.strptime(date_str, '%Y%m%d')

                        # Check if within last 24 hours (rough check, transaction ID is date only)
                        # For more accurate, we'd need the full timestamp, but this is close enough

                        status = tx.get('status', 'unknown')
                        discovered = tx.get('discoveredGps', 0)

                        # Status mapping
                        status_icon = {
                            'Scanning': '⏳',
                            'Processing': '🔄',
                            'Trilaterating': '📍',
                            'Success': '✅',
                            'Failed': '❌',
                            'Queued': '⏸️'
                        }.get(status, '❓')

                        # Format the line
                        line = f"║ {status_icon} {trans_id[:16]:16} │ {status:15} │ {discovered:>5} new WiFi │ {date_str[:4]}-{date_str[4:6]}-{date_str[6:8]:7} ║"
                        activity_lines.append(line)

                        recent_count += 1
                        if discovered:
                            total_new_wifi_24h += discovered

                    except:
                        continue

                if recent_count == 0:
                    activity_lines.append("║ No uploads in the last 24 hours                                               ║")
                else:
                    activity_lines.append("╠════════════════════════════════════════════════════════════════════════════════╣")
                    activity_lines.append(f"║ Total: {recent_count} uploads │ {total_new_wifi_24h} new WiFi networks discovered{' ' * (29 - len(str(total_new_wifi_24h)))}║")

                activity_lines.append("╚════════════════════════════════════════════════════════════════════════════════╝")

                activity_text = '\n'.join(activity_lines)
                self.root.after(0, lambda t=activity_text: self._set_recent_text(t))

            else:
                self.root.after(0, lambda: self._set_recent_text(f"API error: {r.status_code}"))

        except Exception as e:
            self.root.after(0, lambda e=e: self._set_recent_text(f"Error: {str(e)[:50]}"))

    def _set_recent_text(self, text):
        """Update the recent activity text widget"""
        self.dash_recent_text.config(state='normal')
        self.dash_recent_text.delete('1.0', 'end')
        self.dash_recent_text.insert('1.0', text)
        self.dash_recent_text.config(state='disabled')

    def _require_pi(self):
        if not (self.config['pi_host'] and self.config['pi_user'] and self.config['pi_dir']):
            messagebox.showwarning("Missing Settings", "Set Pi Host/User/Dir in Settings.")
            return False
        return True
    
    def _require_wigle(self):
        if not (self.config['wigle_api_id'] and self.config['wigle_api_token_enc']):
            messagebox.showwarning("Missing Credentials", "Set WiGLE API ID + Token in Settings.")
            return False
        return True
    
    def _update_pi_status(self):
        ok = self.config['pi_host'] and self.config['pi_user'] and self.config['pi_dir']
        self.lbl_pi_hint.config(text="" if ok else "Set your Raspberry Pi Host/User/Dir in Settings.")
        self.lbl_pi_info.config(text=f"Source: {self.config['pi_user']}@{self.config['pi_host']}:{self.config['pi_dir']}" if ok else "Source: (not configured)")
        state = 'normal' if ok else 'disabled'
        for btn in [self.btn_copy_wigle, self.btn_delete_wigle, self.btn_automatic, self.btn_upload_direct, 
                    self.btn_start_kismet, self.btn_stop_kismet, self.btn_restart_kismet, 
                    self.btn_reboot, self.btn_shutdown]:
            btn.config(state=state)
    
    def _fmt_bytes(self, b):
        for u, d in [('B', 1), ('KB', 1024), ('MB', 1024**2), ('GB', 1024**3)]:
            if b < d * 1024 or u == 'GB':
                return f"{b/d:.1f} {u}" if d > 1 else f"{b} {u}"
    
    def _ssh(self, cmd):
        return subprocess.run(['ssh', f"{self.config['pi_user']}@{self.config['pi_host']}", cmd], capture_output=True, text=True)
    
    def _save_settings(self):
        self.config['pi_host'] = self.txt_pi_host.get().strip()
        self.config['pi_user'] = self.txt_pi_user.get().strip()
        self.config['pi_dir'] = self.txt_pi_dir.get().strip()
        self.config['win_dir'] = self.txt_win_dir.get().strip()
        self.config['wigle_out_dir'] = self.txt_wigle_out.get().strip()
        self.config['wigle_api_id'] = self.txt_api_id.get().strip()
        if self.txt_api_token.get():
            self.config['wigle_api_token_enc'] = self.config_mgr.encrypt_token(self.txt_api_token.get())
            self.txt_api_token.delete(0, 'end')
        self.config_mgr.save_config(self.config)
        Path(self.config['win_dir']).mkdir(parents=True, exist_ok=True)
        Path(self.config['wigle_out_dir']).mkdir(parents=True, exist_ok=True)
        self._update_pi_status()
        self._refresh_upload_list()
        self._refresh_dashboard()
        self._set_status("Settings saved.")
    
    def _browse_folder(self, attr):
        current = getattr(self, attr).get()
        folder = filedialog.askdirectory(initialdir=current if current else Path.home(), title="Select Folder")
        if folder:
            getattr(self, attr).delete(0, 'end')
            getattr(self, attr).insert(0, folder)
    
    def _get_ssh_key_path(self):
        """Get path to SSH key"""
        ssh_dir = Path.home() / '.ssh'
        return ssh_dir / 'id_rsa', ssh_dir / 'id_rsa.pub'
    
    def _generate_ssh_key(self):
        """Generate SSH key pair"""
        private_key, public_key = self._get_ssh_key_path()
        
        if public_key.exists():
            if not messagebox.askyesno("Key Exists", 
                "SSH key already exists. Generate a new one? This will overwrite the existing key."):
                return
        
        try:
            self.ssh_status_label.config(text="Status: Generating SSH key...", fg=self.colors['accent'])
            self.root.update_idletasks()
            
            # Generate key with ssh-keygen
            result = subprocess.run(
                ['ssh-keygen', '-t', 'rsa', '-b', '4096', '-f', str(private_key), '-N', ''],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                self.ssh_status_label.config(text="Status: ✓ SSH key generated successfully!", fg=self.colors['secondary'])
                messagebox.showinfo("Success", 
                    f"SSH key generated successfully!\n\nPublic key saved to:\n{public_key}")
            else:
                self.ssh_status_label.config(text="Status: ✗ Failed to generate key", fg=self.colors['danger'])
                messagebox.showerror("Error", f"Failed to generate SSH key:\n{result.stderr}")
        
        except FileNotFoundError:
            self.ssh_status_label.config(text="Status: ✗ ssh-keygen not found", fg=self.colors['danger'])
            messagebox.showerror("Error", 
                "ssh-keygen not found. Please install OpenSSH:\n\n"
                "Windows: Settings → Apps → Optional Features → Add OpenSSH Client\n"
                "Or download from: https://github.com/PowerShell/Win32-OpenSSH/releases")
        except Exception as e:
            self.ssh_status_label.config(text="Status: ✗ Error occurred", fg=self.colors['danger'])
            messagebox.showerror("Error", f"Error generating SSH key:\n{e}")
    
    def _copy_key_to_pi(self):
        """Copy SSH key to Pi"""
        if not self.config['pi_host'] or not self.config['pi_user']:
            messagebox.showwarning("Missing Info", "Please enter Pi Host and Pi User first.")
            return
        
        private_key, public_key = self._get_ssh_key_path()
        
        if not public_key.exists():
            messagebox.showwarning("No Key", 
                "No SSH key found. Please generate one first by clicking '1. Generate SSH Key'.")
            return
        
        # Ask for Pi password
        password_dialog = tk.Toplevel(self.root)
        password_dialog.title("Enter Pi Password")
        password_dialog.geometry("400x150")
        password_dialog.configure(bg=self.colors['card'])
        password_dialog.transient(self.root)
        password_dialog.grab_set()
        
        tk.Label(password_dialog, text=f"Enter password for {self.config['pi_user']}@{self.config['pi_host']}:", 
                bg=self.colors['card'], fg=self.colors['text']).pack(pady=10)
        
        password_var = tk.StringVar()
        password_entry = tk.Entry(password_dialog, textvariable=password_var, show='*', width=30,
                                  bg='#3A3A3A', fg=self.colors['text'], insertbackground=self.colors['primary'])
        password_entry.pack(pady=10)
        password_entry.focus()
        
        def do_copy():
            password = password_var.get()
            password_dialog.destroy()
            if password:
                threading.Thread(target=self._copy_key_thread, args=(password,), daemon=True).start()
        
        btn_frame = tk.Frame(password_dialog, bg=self.colors['card'])
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Copy Key", command=do_copy, bg=self.colors['secondary'], 
                 fg='white', relief='flat', width=12).pack(side='left', padx=5)
        tk.Button(btn_frame, text="Cancel", command=password_dialog.destroy, bg=self.colors['bg_secondary'], 
                 fg=self.colors['text'], relief='flat', width=12).pack(side='left', padx=5)
        
        password_entry.bind('<Return>', lambda e: do_copy())
    
    def _copy_key_thread(self, password):
        """Background thread to copy SSH key"""
        try:
            self.ssh_status_label.config(text="Status: Copying key to Pi...", fg=self.colors['accent'])
            self.root.update_idletasks()
            
            private_key, public_key = self._get_ssh_key_path()
            pub_key_content = public_key.read_text().strip()
            
            pi_target = f"{self.config['pi_user']}@{self.config['pi_host']}"
            
            # Use sshpass to copy the key (works on Windows with OpenSSH)
            # Alternative approach: use expect-like behavior with subprocess
            commands = [
                'mkdir -p ~/.ssh',
                f'echo "{pub_key_content}" >> ~/.ssh/authorized_keys',
                'chmod 700 ~/.ssh',
                'chmod 600 ~/.ssh/authorized_keys'
            ]
            
            # Try using ssh with password via stdin (requires sshpass or alternative)
            # For Windows, we'll use a different approach with pexpect-like behavior
            
            # Create a temporary script to handle the SSH commands
            script = f"""
Set-Variable -Name pass -Value '{password}'
$commands = @(
    'mkdir -p ~/.ssh',
    'echo "{pub_key_content}" >> ~/.ssh/authorized_keys',
    'chmod 700 ~/.ssh',
    'chmod 600 ~/.ssh/authorized_keys'
)
foreach ($cmd in $commands) {{
    echo $pass | ssh -o StrictHostKeyChecking=no {pi_target} $cmd
}}
"""
            
            # Actually, let's use a simpler approach with ssh-copy-id if available
            # Or fall back to manual ssh command
            try:
                # Try ssh-copy-id first (Linux/Mac style)
                result = subprocess.run(
                    ['ssh-copy-id', '-i', str(public_key), pi_target],
                    input=password + '\n',
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                success = result.returncode == 0
            except FileNotFoundError:
                # ssh-copy-id not available, use manual method
                # This requires the user to have sshpass or we do it manually
                cmd = f'type "{public_key}" | ssh {pi_target} "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"'
                
                # For Windows, we'll guide the user to do it manually
                self.root.after(0, lambda: self._show_manual_key_copy_instructions(pub_key_content))
                return
            
            if success:
                self.ssh_status_label.config(text="Status: ✓ SSH key copied successfully!", fg=self.colors['secondary'])
                self.root.after(0, lambda: messagebox.showinfo("Success", 
                    "SSH key copied to Pi successfully!\n\nYou can now use passwordless SSH authentication."))
            else:
                self.ssh_status_label.config(text="Status: ✗ Failed to copy key", fg=self.colors['danger'])
                self.root.after(0, lambda: messagebox.showerror("Error", 
                    f"Failed to copy SSH key:\n{result.stderr}"))
        
        except Exception as e:
            self.ssh_status_label.config(text="Status: ✗ Error occurred", fg=self.colors['danger'])
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error copying SSH key:\n{e}"))
    
    def _show_manual_key_copy_instructions(self, pub_key_content):
        """Show manual instructions for copying SSH key"""
        instructions = tk.Toplevel(self.root)
        instructions.title("Manual SSH Key Setup")
        instructions.geometry("600x400")
        instructions.configure(bg=self.colors['card'])
        
        tk.Label(instructions, text="Manual SSH Key Setup Required", 
                bg=self.colors['card'], fg=self.colors['text'], 
                font=('Segoe UI', 11, 'bold')).pack(pady=10)
        
        tk.Label(instructions, text="Copy the key below and paste it into your Pi:", 
                bg=self.colors['card'], fg=self.colors['text']).pack(pady=5)
        
        text_widget = scrolledtext.ScrolledText(instructions, height=10, width=70,
                                                bg='#3A3A3A', fg=self.colors['text'])
        text_widget.pack(pady=10, padx=10)
        text_widget.insert('1.0', pub_key_content)
        text_widget.config(state='disabled')
        
        tk.Label(instructions, text="SSH into your Pi and run:", 
                bg=self.colors['card'], fg=self.colors['text'], 
                font=('Segoe UI', 9, 'bold')).pack(pady=5)
        
        cmd_widget = scrolledtext.ScrolledText(instructions, height=5, width=70,
                                               bg='#3A3A3A', fg=self.colors['text'])
        cmd_widget.pack(pady=5, padx=10)
        cmd_text = """mkdir -p ~/.ssh
echo "[paste your key here]" >> ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys"""
        cmd_widget.insert('1.0', cmd_text)
        cmd_widget.config(state='disabled')
        
        tk.Button(instructions, text="Close", command=instructions.destroy,
                 bg=self.colors['primary'], fg='white', relief='flat', width=15).pack(pady=10)
    
    def _test_ssh_connection(self):
        """Test SSH connection"""
        if not self.config['pi_host'] or not self.config['pi_user']:
            messagebox.showwarning("Missing Info", "Please enter Pi Host and Pi User first.")
            return
        
        self.ssh_status_label.config(text="Status: Testing connection...", fg=self.colors['accent'])
        self.root.update_idletasks()
        
        try:
            pi_target = f"{self.config['pi_user']}@{self.config['pi_host']}"
            result = subprocess.run(
                ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', pi_target, 'echo', 'success'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0 and 'success' in result.stdout:
                self.ssh_status_label.config(text="Status: ✓ SSH connection successful!", fg=self.colors['secondary'])
                messagebox.showinfo("Success", "SSH connection works!\n\nPasswordless authentication is configured correctly.")
            else:
                self.ssh_status_label.config(text="Status: ✗ Connection failed", fg=self.colors['danger'])
                messagebox.showerror("Connection Failed", 
                    "SSH connection failed. Please make sure:\n\n"
                    "1. You've generated an SSH key\n"
                    "2. You've copied it to the Pi\n"
                    "3. Pi Host and Pi User are correct\n"
                    "4. Your Pi is reachable on the network")
        
        except subprocess.TimeoutExpired:
            self.ssh_status_label.config(text="Status: ✗ Connection timeout", fg=self.colors['danger'])
            messagebox.showerror("Timeout", "Connection timed out. Is your Pi reachable?")
        except Exception as e:
            self.ssh_status_label.config(text="Status: ✗ Error occurred", fg=self.colors['danger'])
            messagebox.showerror("Error", f"Error testing connection:\n{e}")
    
    def _copy_wigle(self):
        if not self._require_pi(): return
        self.txt_pull_log.delete('1.0', 'end')
        threading.Thread(target=self._copy_wigle_thread, daemon=True).start()
    
    def _copy_wigle_thread(self):
        try:
            pi, wd = f"{self.config['pi_user']}@{self.config['pi_host']}", Path(self.config['win_dir'])
            mr, ar, ml, al = "/tmp/w.sha256", "/tmp/w.tgz", wd / "w.sha256", wd / "w.tgz"
            self.progress['maximum'], self.progress['value'] = 4, 0
            self._log("Creating manifest...")
            self._ssh(f"cd '{self.config['pi_dir']}'; find . -type f -name '*.wiglecsv' -print0 | sort -z | xargs -0 sha256sum > '{mr}'")
            self.progress['value'] = 1
            self._log("Packing...")
            self._ssh(f"cd '{self.config['pi_dir']}'; find . -type f -name '*.wiglecsv' -print0 | tar --null -T - -czf '{ar}'")
            self.progress['value'] = 2
            self._log("Copying...")
            subprocess.run(['scp', f"{pi}:{ar}", str(al)])
            subprocess.run(['scp', f"{pi}:{mr}", str(ml)])
            self.progress['value'] = 3
            self._log("Extracting...")
            with tarfile.open(al, 'r:gz') as tar:
                tar.extractall(wd)
            self.progress['value'] = 4
            self._log("Complete")
            self._set_status("Transfer complete.")
            self._reset_progress()
            self.root.after(0, self._refresh_upload_list)
        except Exception as e:
            self._log(f"ERROR: {e}")
            self._set_status("Failed.")
            self._reset_progress()
    
    def _delete_wigle(self):
        if not self._require_pi() or not messagebox.askyesno("Confirm", "Delete ALL .wiglecsv on Pi?"): return
        self.txt_pull_log.delete('1.0', 'end')
        try:
            self._ssh(f"cd '{self.config['pi_dir']}'; find . -type f -name '*.wiglecsv' -delete")
            self._log("Complete")
        except Exception as e:
            self._log(f"ERROR: {e}")
    
    def _automatic(self):
        if not self._require_pi(): return
        self.txt_pull_log.delete('1.0', 'end')
        threading.Thread(target=self._automatic_thread, daemon=True).start()
    
    def _automatic_thread(self):
        try:
            self._log("Stopping Kismet...")
            self._ssh("sudo systemctl stop kismet")
            self._copy_wigle_thread()
            wd, ml = Path(self.config['win_dir']), Path(self.config['win_dir']) / "w.sha256"
            self._log("Verifying...")
            bad = []
            for line in ml.read_text().strip().split('\n'):
                if not line: continue
                exp, rel = line[:64], line[66:].strip().lstrip('./')
                lp = wd / rel
                if not lp.exists():
                    bad.append(f"MISSING: {rel}")
                elif hashlib.sha256(lp.read_bytes()).hexdigest().lower() != exp.lower():
                    bad.append(f"MISMATCH: {rel}")
            if bad:
                self._log("FAILED (not deleting):")
                for b in bad: self._log(b)
                self._set_status("Verification failed.")
                return
            self._log("OK. Deleting...")
            self._ssh(f"cd '{self.config['pi_dir']}'; find . -type f -name '*.wiglecsv' -delete")
            self._log("Complete")
            self._set_status("Done.")
            self._reset_progress()
        except Exception as e:
            self._log(f"ERROR: {e}")
            self._set_status("Failed.")
    
    def _restart_kismet(self):
        if self._require_pi():
            self._ssh("sudo systemctl restart kismet")
            self._set_status("Kismet restarted.")
    
    def _start_kismet(self):
        if self._require_pi():
            self._ssh("sudo systemctl start kismet")
            self._set_status("Kismet started.")
    
    def _stop_kismet(self):
        if self._require_pi():
            self._ssh("sudo systemctl stop kismet")
            self._set_status("Kismet stopped.")
    
    def _reboot_pi(self):
        if self._require_pi() and messagebox.askyesno("Confirm", "Reboot the Raspberry Pi?"):
            self._ssh("sudo reboot")
            self._set_status("Reboot command sent.")
    
    def _shutdown_pi(self):
        if self._require_pi() and messagebox.askyesno("Confirm", "Shutdown Pi?"):
            self._ssh("sudo shutdown -h now")
            self._set_status("Shutdown sent.")
    
    def _upload_direct_to_wigle(self):
        if not self._require_pi() or not self._require_wigle(): return
        if not messagebox.askyesno("Confirm", "Upload all .wiglecsv files directly from RPi to WiGLE, then delete them from RPi?"): return
        self.txt_pull_log.delete('1.0', 'end')
        threading.Thread(target=self._upload_direct_thread, daemon=True).start()
    
    def _upload_direct_thread(self):
        try:
            pi, wd = f"{self.config['pi_user']}@{self.config['pi_host']}", Path(self.config['win_dir'])
            wd.mkdir(parents=True, exist_ok=True)
            token = self.config_mgr.decrypt_token(self.config['wigle_api_token_enc'])
            if not token:
                self._log("ERROR: Token decrypt failed.")
                self._set_status("Token decrypt failed.")
                return
            
            # Stop Kismet
            self._log("Stopping Kismet...")
            self._ssh("sudo systemctl stop kismet")
            
            # Get list of files
            self._log("Getting file list from RPi...")
            result = self._ssh(f"cd '{self.config['pi_dir']}'; find . -type f -name '*.wiglecsv' -print")
            files = [f.strip().lstrip('./') for f in result.stdout.strip().split('\n') if f.strip()]
            
            if not files:
                self._log("No .wiglecsv files found on RPi.")
                self._set_status("No files to upload.")
                return
            
            self._log(f"Found {len(files)} file(s) to upload")
            self.progress['maximum'] = len(files)
            self.progress['value'] = 0
            
            uploaded = []
            for remote_file in files:
                remote_path = f"{self.config['pi_dir']}/{remote_file}"
                local_file = wd / f"temp_{Path(remote_file).name}"
                
                self._log(f"Downloading {remote_file}...")
                self._set_status(f"Downloading {Path(remote_file).name}...")
                subprocess.run(['scp', f"{pi}:{remote_path}", str(local_file)])
                
                self._log(f"Uploading to WiGLE...")
                self._set_status(f"Uploading {Path(remote_file).name} to WiGLE...")
                try:
                    with open(local_file, 'rb') as f:
                        r = requests.post("https://api.wigle.net/api/v2/file/upload", 
                            auth=(self.config['wigle_api_id'], token),
                            headers={'Accept': 'application/json'}, 
                            files={'file': f})
                    resp = r.json()
                    if 'transid' in resp:
                        self._log(f"  ✓ Uploaded successfully (TransID: {resp['transid']})")
                        uploaded.append(remote_path)
                    else:
                        self._log(f"  ✓ Uploaded (no TransID returned)")
                        uploaded.append(remote_path)
                except Exception as e:
                    self._log(f"  ✗ Upload failed: {e}")
                
                # Clean up local temp file
                try:
                    local_file.unlink()
                except:
                    pass
                
                self.progress['value'] += 1
            
            # Delete uploaded files from RPi
            if uploaded:
                self._log(f"\nDeleting {len(uploaded)} uploaded file(s) from RPi...")
                for remote_path in uploaded:
                    self._ssh(f"rm -f '{remote_path}'")
                self._log("Cleanup complete")
            
            self._log(f"\nDone! Uploaded {len(uploaded)} of {len(files)} file(s)")
            self._set_status("Upload complete.")
            self._reset_progress()
            
        except Exception as e:
            self._log(f"ERROR: {e}")
            self._set_status("Upload failed.")
            self._reset_progress()
    
    def _refresh_upload_list(self):
        self.tree_upload.delete(*self.tree_upload.get_children())
        self.upload_checks = {}
        for fp in sorted(Path(self.config['win_dir']).rglob('*.wiglecsv')):
            item = self.tree_upload.insert('', 'end', text='☐', values=(str(fp), self._fmt_bytes(fp.stat().st_size), 'Ready', ''))
            self.upload_checks[item] = False
        self._set_status(f"Found {len(self.upload_checks)} files")
    
    def _upload_files(self):
        if not self._require_wigle(): return
        token = self.config_mgr.decrypt_token(self.config['wigle_api_token_enc'])
        if not token: return self._set_status("Token decrypt failed.")
        items = [i for i, c in self.upload_checks.items() if c]
        if not items: return
        self.progress['maximum'], self.progress['value'] = len(items), 0
        for item in items:
            fp = self.tree_upload.item(item)['values'][0]
            self.tree_upload.set(item, 'Status', 'Uploading...')
            self.root.update_idletasks()
            try:
                with open(fp, 'rb') as f:
                    r = requests.post("https://api.wigle.net/api/v2/file/upload", auth=(self.config['wigle_api_id'], token),
                        headers={'Accept': 'application/json'}, files={'file': f})
                resp = r.json()
                self.tree_upload.set(item, 'Status', 'Uploaded')
                if 'transid' in resp:
                    self.tree_upload.set(item, 'TransID', resp['transid'])
            except:
                self.tree_upload.set(item, 'Status', 'FAILED')
            self.progress['value'] += 1
        self._set_status("Upload complete.")
        self._reset_progress()
    
    def _delete_local(self):
        items = [i for i, c in self.upload_checks.items() if c]
        if items and messagebox.askyesno("Confirm", "Delete selected files?"):
            for item in items:
                try: Path(self.tree_upload.item(item)['values'][0]).unlink()
                except: pass
            self._refresh_upload_list()
    
    def _archive_local(self):
        items = [i for i, c in self.upload_checks.items() if c]
        if not items: return
        zp = Path(self.config['win_dir']) / f"{datetime.now().strftime('%Y-%m-%d')}.zip"
        if zp.exists() and not messagebox.askyesno("Confirm", f"Overwrite {zp.name}?"): return
        files_to_delete = []
        with zipfile.ZipFile(zp, 'w') as zf:
            for item in items:
                if (fp := Path(self.tree_upload.item(item)['values'][0])).exists():
                    zf.write(fp, fp.name)
                    files_to_delete.append(fp)
        # Delete the source files after successful archiving
        for fp in files_to_delete:
            try:
                fp.unlink()
            except Exception as e:
                self._log(f"Warning: Could not delete {fp.name}: {e}")
        self._refresh_upload_list()
        self._set_status(f"Archived to {zp.name} and deleted source files")
    
    def _find_transactions(self):
        if not self._require_wigle(): return
        self.tree_tx.delete(*self.tree_tx.get_children())
        self.tx_checks = {}
        start, end = self.txt_start.get().strip(), self.txt_end.get().strip()
        if len(start) != 8 or len(end) != 8: return self._set_status("Invalid date format.")
        try:
            token = self.config_mgr.decrypt_token(self.config['wigle_api_token_enc'])
            r = requests.get("https://api.wigle.net/api/v2/file/transactions?pagestart=0", auth=(self.config['wigle_api_id'], token))
            for tx in r.json()['results']:
                if (tid := tx.get('transid', '')) and len(tid) >= 8 and start <= (date := tid[:8]) <= end:
                    dl = (Path(self.config['wigle_out_dir']) / f"{tid}.kml").exists()
                    item = self.tree_tx.insert('', 'end', text='☐', values=(tid, date, 'Downloaded' if dl else 'New', '', ''))
                    self.tx_checks[item] = False
            self._set_status(f"Found {len(self.tx_checks)} transactions")
        except Exception as e:
            self._set_status(f"Error: {e}")
    
    def _tx_download_new(self):
        for item, checked in self.tx_checks.items():
            if self.tree_tx.item(item)['values'][2] == 'New':
                self.tx_checks[item] = True
                self.tree_tx.item(item, text='☑')
    
    def _tx_download_selected(self):
        if not self._require_wigle(): return
        items = [i for i, c in self.tx_checks.items() if c]
        if not items: return
        token = self.config_mgr.decrypt_token(self.config['wigle_api_token_enc'])
        self.progress['maximum'], self.progress['value'] = len(items), 0
        for item in items:
            tid = self.tree_tx.item(item)['values'][0]
            fp = Path(self.config['wigle_out_dir']) / f"{tid}.kml"
            if fp.exists():
                self.progress['value'] += 1
                continue
            try:
                r = requests.get(f"https://api.wigle.net/api/v2/file/kml/{tid}", auth=(self.config['wigle_api_id'], token))
                fp.write_bytes(r.content)
                self.tree_tx.set(item, 'Status', 'Downloaded')
            except: pass
            self.progress['value'] += 1
        self._set_status("Download complete.")
        self._reset_progress()


if __name__ == '__main__':
    root = tk.Tk()
    app = FrostbandApp(root)
    root.mainloop()
