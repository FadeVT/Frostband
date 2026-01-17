# Frostband

A modern, cross-platform wardriving management tool for Kismet and WiGLE with a sleek dark mode interface.

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-brightgreen)
![License](https://img.shields.io/badge/license-MIT-orange)

## Features

### 📡 Raspberry Pi Management
- **Automated workflow**: Stop Kismet → Copy files → Verify integrity → Delete from Pi
- **Direct WiGLE upload**: Upload files from Pi to WiGLE without local storage
- **Remote control**: Start/Stop/Restart Kismet service
- **System control**: Reboot or shutdown your Pi remotely
- **File management**: Copy or delete .wiglecsv files from your Pi

### 📤 Local File Management
- Upload .wiglecsv files to WiGLE
- Archive files locally
- Batch operations with checkboxes
- Real-time upload progress tracking

### 📥 WiGLE Transactions
- Search transactions by date range
- Download KML files for mapping
- Track download status
- Bulk download operations

### ⚙️ Easy Configuration
- Encrypted credential storage (Windows DPAPI / Fernet)
- One-click SSH key setup
- Automatic connection testing
- Dark mode interface with color-coded buttons

## Screenshots

### RPi Manager (Default View)
![RPi Manager](screenshots/rpi-manager.png)

### WiGLE CSV Upload
![WiGLE Upload](screenshots/wigle-csv.png)

### Transaction Downloads
![Transactions](screenshots/transactions.png)

### Settings & Configuration
![Settings](screenshots/settings.png)

## Installation

### Prerequisites
- **WiGLE account** with API credentials ([Get them here](https://wigle.net/account))

### Windows Installation

1. **Install Python 3.8 or higher**
   - Download from [python.org](https://www.python.org/downloads/)
   - **IMPORTANT**: Check "Add Python to PATH" during installation
   - Verify installation: Open PowerShell and run `python --version`

2. **Install OpenSSH Client** (if not already installed)
   - Settings → Apps → Optional Features → Add a feature
   - Search for "OpenSSH Client" and install
   - Or it may already be installed on Windows 10/11

3. **Install Dependencies**
   ```powershell
   python -m pip install -r requirements.txt
   ```
   
   **Note**: If `pip install` doesn't work, always use `python -m pip` instead.

4. **Run the Application**
   ```powershell
   python frostband.py
   ```

### Linux Installation

1. **Install Python 3.8 or higher**
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install python3 python3-pip
   
   # Fedora
   sudo dnf install python3 python3-pip
   
   # Arch
   sudo pacman -S python python-pip
   ```

2. **Install OpenSSH Client** (usually pre-installed)
   ```bash
   # Ubuntu/Debian
   sudo apt install openssh-client
   
   # Fedora
   sudo dnf install openssh-clients
   
   # Arch
   sudo pacman -S openssh
   ```

3. **Install Dependencies**
   ```bash
   pip3 install -r requirements.txt
   # or
   python3 -m pip install -r requirements.txt
   ```

4. **Run the Application**
   ```bash
   python3 frostband.py
   ```

## Building Standalone Executable (Windows)

For Windows users who want a standalone .exe file:

1. **Install PyInstaller**
   ```powershell
   python -m pip install pyinstaller
   ```

2. **Build the executable**
   ```powershell
   python -m PyInstaller --onefile --windowed --name Frostband --icon=frostband.ico frostband.py
   ```

3. **Find your executable**
   
   The executable will be created in the `dist/` folder.
   
   **Note**: The first build may take a few minutes. The final .exe will be 15-25 MB.

## First-Time Setup

### 1. Configure WiGLE API
1. Go to the **Settings** tab
2. Click "Get API Key →" to open WiGLE account page
3. Copy your API Name and Token
4. Paste into Frostband and click "Save Settings"

### 2. Configure Raspberry Pi Connection
1. Enter your Pi's IP address
2. Enter your Pi username (usually `pi`)
3. Enter the directory where Kismet stores files (e.g., `/home/pi/kismet`)
4. Click "Save Settings"

### 3. Set Up SSH Keys (Recommended)
The app includes automatic SSH key setup for passwordless authentication:

1. Click **"1. Generate SSH Key"** - Creates a new SSH key pair
2. Click **"2. Copy Key to Pi"** - Uploads your key to the Pi (enter password once)
3. Click **"3. Test Connection"** - Verifies everything works

If automatic setup doesn't work, manual instructions will be provided.

### 4. Configure Local Directories
- **Local Kismet Dir**: Where .wiglecsv files are stored on your PC
- **WiGLE Output Dir**: Where downloaded KML files are saved

Use the "Browse..." buttons to select folders easily.

## Usage

### Automatic Workflow (Recommended)
On the **RPi Manager** tab, click **"Automatic (Stop → Copy → Verify → Delete)"**:
- Stops Kismet on your Pi
- Copies all .wiglecsv files to your PC
- Verifies file integrity with SHA-256 hashes
- Deletes files from Pi only if verification passes

### Upload to WiGLE
1. Go to **WiGLE CSV** tab
2. Click "Refresh list" to see your local files
3. Check the files you want to upload
4. Click "Upload"

### Download WiGLE Transactions
1. Go to **Transactions** tab
2. Enter date range (YYYYMMDD format)
3. Click "Find Transactions"
4. Select transactions and click "Download Selected"

## Configuration Files

Settings are stored in:
- **Windows**: `%APPDATA%\Frostband\frostband_config.json`
- **Linux**: `~/.config/Frostband/frostband_config.json`

API tokens are encrypted using:
- **Windows**: DPAPI (Data Protection API)
- **Linux**: Fernet symmetric encryption

## Troubleshooting

### SSH Connection Issues
- Ensure OpenSSH client is installed
- Verify Pi is reachable on the network (`ping <pi-ip>`)
- Check that SSH is enabled on your Pi
- Use "Test Connection" in Settings to diagnose

### WiGLE Upload Failures
- Verify API credentials are correct
- Check internet connection
- Ensure .wiglecsv files are valid Kismet output

### Missing Dependencies
```bash
pip install --upgrade -r requirements.txt
```

## Development

### Project Structure
```
Frostband/
├── frostband.py          # Main application
├── frostband.ico         # Application icon
├── requirements.txt      # Python dependencies
├── README.md            # This file
└── .gitignore           # Git ignore rules
```

### Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## Credits

Developed for the wardriving community. Built with:
- Python & tkinter for the GUI
- Requests for API communication
- Cryptography for secure credential storage

## License

MIT License - see LICENSE file for details

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

---

**Happy Wardriving! 📡**