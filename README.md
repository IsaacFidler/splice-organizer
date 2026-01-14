# Splice Sample Organizer

Automatically organizes your Splice samples into a flat, categorized folder structure for easier browsing in Ableton Live (or any DAW).

## The Problem

Splice downloads samples into deeply nested folders (often 10+ levels deep). When browsing from Ableton's Places, you have to dig through multiple layers just to find a kick drum.

## The Solution

This script watches your Splice folder and creates symlinks in an organized structure:

```
~/Splice-Organized/
├── All/                    # Every sample, flat (for random browsing)
├── One_Shots/              # Categorized one-shots
│   ├── Kicks/
│   ├── Snares/
│   ├── HiHats/
│   ├── Cymbals/
│   ├── Percussion/
│   ├── FX/
│   ├── Synths/
│   ├── Bass/
│   ├── Vocals/
│   └── Other/
├── Loops/                  # Categorized loops
│   ├── Drums/
│   ├── Bass/
│   ├── Synths/
│   ├── Pads/
│   ├── FX/
│   ├── Percussion/
│   ├── Vocals/
│   └── Other/
└── Genres/                 # Organized by genre
    ├── Electronic/
    │   ├── Techno/
    │   ├── House/
    │   ├── Drum_and_Bass/
    │   ├── Dubstep/
    │   ├── Garage/
    │   ├── Trap/
    │   ├── Drill/
    │   ├── Ambient/
    │   ├── Lo-Fi/
    │   ├── Drum_Machines/  # 808, 909, etc.
    │   └── ...
    ├── Live/
    │   ├── Rock/
    │   ├── Punk/
    │   ├── Darkwave/
    │   ├── Jazz/
    │   ├── Dub/
    │   ├── Classical/
    │   ├── Acoustic/
    │   └── ...
    └── Other/              # Samples with no genre match
```

Your original Splice folder stays untouched - the script only creates symlinks.

## Installation

```bash
# Clone the repo
git clone https://github.com/IsaacFidler/splice-organizer.git ~/.splice-organizer

# Create virtual environment
cd ~/.splice-organizer
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run initial sync
python splice_organizer.py --no-watch
```

## Usage

### Manual sync
```bash
python splice_organizer.py --no-watch
```

### Watch mode (auto-detect new samples)
```bash
python splice_organizer.py
```

### CLI Options
```
--resync      Force reprocess all files (clears existing symlinks)
--stats       Show categorization statistics
--validate    Remove broken symlinks
--dry-run     Preview changes without creating symlinks
--no-watch    Run initial sync only, don't watch for changes
-v, --verbose Enable verbose logging
```

## Auto-start on macOS (launchd)

Create `~/Library/LaunchAgents/com.splice-organizer.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.splice-organizer</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/YOUR_USERNAME/.splice-organizer/venv/bin/python</string>
        <string>/Users/YOUR_USERNAME/.splice-organizer/splice_organizer.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/Splice-Organized/organizer.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/Splice-Organized/organizer.stderr.log</string>
</dict>
</plist>
```

Then load it:
```bash
launchctl load ~/Library/LaunchAgents/com.splice-organizer.plist
```

## Configuration

Edit the paths at the top of `splice_organizer.py` if your Splice folder is in a different location:

```python
SPLICE_PACKS_DIR = Path.home() / "Splice" / "sounds" / "packs"
ORGANIZED_DIR = Path.home() / "Splice-Organized"
```

## How Categorization Works

1. **One-Shot vs Loop**: Detected from folder path (`/One_Shots/` vs `/Loops/`) and filename patterns
2. **Instrument Category**: Parsed from filename and parent folder names (e.g., `drums_kick_punch` → Kicks)
3. **Genre Detection**: Parsed from pack name and folder structure using keyword matching
   - Samples can match multiple genres and will appear in each folder
   - E.g., "UK Dubstep Drums" → appears in both `Electronic/Dubstep/` and `Live/Dub/`
4. **Collision Handling**: Files are prefixed with pack name (e.g., `808_Essentials__kick_01.wav`)

## Requirements

- Python 3.8+
- macOS (uses FSEvents for file watching, but should work on Linux with inotify)
- [watchdog](https://pypi.org/project/watchdog/)

## License

MIT
