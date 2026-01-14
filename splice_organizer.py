#!/usr/bin/env python3
"""
Splice Sample Organizer
Watches Splice folder and creates organized symlinks for easier browsing in Ableton.
"""

import argparse
import hashlib
import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configuration
SPLICE_PACKS_DIR = Path.home() / "Splice" / "sounds" / "packs"
ORGANIZED_DIR = Path.home() / "Splice-Organized"
STATE_FILE = ORGANIZED_DIR / ".organizer_state.json"
LOG_FILE = ORGANIZED_DIR / "organizer.log"

# Categorization patterns - using (?:^|[\s_/]) as word boundary to match underscores
# Order matters: more specific patterns should come first within each category
ONESHOT_CATEGORIES = {
    'Kicks': [r'(?:^|[\s_/])kicks?(?:[\s_/]|$)', r'(?:^|[\s_/])kck(?:[\s_/]|$)',
              r'(?:^|[\s_/])bd(?:[\s_/]|$)', r'(?:^|[\s_/])bass[_\s]?drum'],
    'Snares': [r'(?:^|[\s_/])snares?(?:[\s_/]|$)', r'(?:^|[\s_/])snr(?:[\s_/]|$)',
               r'(?:^|[\s_/])sd(?:[\s_/]|$)', r'(?:^|[\s_/])rimshot', r'(?:^|[\s_/])claps?(?:[\s_/]|$)'],
    'HiHats': [r'hi[_\s-]?hats?', r'(?:^|[\s_/])hats?(?:[\s_/]|$)', r'(?:^|[\s_/])hh(?:[\s_/]|$)',
               r'(?:^|[\s_/])closed(?:[\s_/]|$)', r'(?:^|[\s_/])open(?:[\s_/]|$)'],
    'Cymbals': [r'(?:^|[\s_/])cymbals?(?:[\s_/]|$)', r'(?:^|[\s_/])crash', r'(?:^|[\s_/])ride(?:[\s_/]|$)',
                r'(?:^|[\s_/])china', r'(?:^|[\s_/])splash'],
    'Percussion': [r'(?:^|[\s_/])percs?(?:[\s_/]|$)', r'(?:^|[\s_/])percussion', r'(?:^|[\s_/])toms?(?:[\s_/]|$)',
                   r'(?:^|[\s_/])bongo', r'(?:^|[\s_/])conga', r'(?:^|[\s_/])shaker',
                   r'(?:^|[\s_/])tambourine', r'(?:^|[\s_/])cowbell', r'(?:^|[\s_/])claves',
                   r'(?:^|[\s_/])triangle', r'(?:^|[\s_/])rim(?:[\s_/]|$)'],
    'FX': [r'(?:^|[\s_/])fx(?:[\s_/]|$)', r'(?:^|[\s_/])effects?(?:[\s_/]|$)', r'(?:^|[\s_/])riser',
           r'(?:^|[\s_/])downlifter', r'(?:^|[\s_/])impacts?(?:[\s_/]|$)',
           r'(?:^|[\s_/])sweep', r'(?:^|[\s_/])transition', r'(?:^|[\s_/])foley',
           r'(?:^|[\s_/])noise', r'(?:^|[\s_/])textures?(?:[\s_/]|$)'],
    'Synths': [r'(?:^|[\s_/])synths?(?:[\s_/]|$)', r'(?:^|[\s_/])leads?(?:[\s_/]|$)',
               r'(?:^|[\s_/])pads?(?:[\s_/]|$)', r'(?:^|[\s_/])chords?(?:[\s_/]|$)',
               r'(?:^|[\s_/])arps?(?:[\s_/]|$)', r'(?:^|[\s_/])plucks?(?:[\s_/]|$)',
               r'(?:^|[\s_/])stabs?(?:[\s_/]|$)', r'(?:^|[\s_/])keys(?:[\s_/]|$)',
               r'(?:^|[\s_/])piano', r'(?:^|[\s_/])organ'],
    'Bass': [r'(?:^|[\s_/])bass(?:[\s_/]|$)', r'(?:^|[\s_/])sub(?:[\s_/]|$)',
             r'(?:^|[\s_/])808(?:[\s_/]|$)', r'(?:^|[\s_/])reese'],
    'Vocals': [r'(?:^|[\s_/])vocals?(?:[\s_/]|$)', r'(?:^|[\s_/])vox(?:[\s_/]|$)',
               r'(?:^|[\s_/])voice', r'(?:^|[\s_/])spoken', r'(?:^|[\s_/])chant',
               r'(?:^|[\s_/])adlib', r'(?:^|[\s_/])shout'],
}

LOOP_CATEGORIES = {
    'Drums': [r'(?:^|[\s_/])drums?(?:[\s_/]|$)', r'(?:^|[\s_/])beats?(?:[\s_/]|$)',
              r'(?:^|[\s_/])groove', r'(?:^|[\s_/])breaks?(?:[\s_/]|$)',
              r'(?:^|[\s_/])tops?(?:[\s_/]|$)', r'(?:^|[\s_/])full(?:[\s_/]|$)'],
    'Bass': [r'(?:^|[\s_/])bass(?:[\s_/]|$)', r'(?:^|[\s_/])sub(?:[\s_/]|$)',
             r'(?:^|[\s_/])808(?:[\s_/]|$)', r'(?:^|[\s_/])reese'],
    'Synths': [r'(?:^|[\s_/])synths?(?:[\s_/]|$)', r'(?:^|[\s_/])leads?(?:[\s_/]|$)',
               r'(?:^|[\s_/])arps?(?:[\s_/]|$)', r'(?:^|[\s_/])plucks?(?:[\s_/]|$)',
               r'(?:^|[\s_/])stabs?(?:[\s_/]|$)', r'(?:^|[\s_/])chords?(?:[\s_/]|$)',
               r'(?:^|[\s_/])keys(?:[\s_/]|$)', r'melod'],
    'Pads': [r'(?:^|[\s_/])pads?(?:[\s_/]|$)', r'(?:^|[\s_/])atmosphere',
             r'(?:^|[\s_/])ambient', r'(?:^|[\s_/])textures?(?:[\s_/]|$)', r'(?:^|[\s_/])drone'],
    'FX': [r'(?:^|[\s_/])fx(?:[\s_/]|$)', r'(?:^|[\s_/])effects?(?:[\s_/]|$)',
           r'(?:^|[\s_/])riser', r'(?:^|[\s_/])downlifter', r'(?:^|[\s_/])transition'],
    'Percussion': [r'(?:^|[\s_/])percs?(?:[\s_/]|$)', r'(?:^|[\s_/])hats?(?:[\s_/]|$)',
                   r'(?:^|[\s_/])shaker', r'(?:^|[\s_/])tambourine'],
    'Vocals': [r'(?:^|[\s_/])vocals?(?:[\s_/]|$)', r'(?:^|[\s_/])vox(?:[\s_/]|$)',
               r'(?:^|[\s_/])voice', r'(?:^|[\s_/])hook', r'(?:^|[\s_/])chant'],
}

# Genre categories - keywords map to genre buckets
# Samples can match multiple genres and will be symlinked to each
GENRE_CATEGORIES = {
    'Electronic': {
        'Techno': [r'techno', r'industrial', r'minimal', r'ebm', r'hard[_\s-]?techno',
                   r'acid[_\s-]?techno', r'berlin', r'warehouse'],
        'House': [r'house', r'deep[_\s-]?house', r'tech[_\s-]?house', r'future[_\s-]?house',
                  r'bass[_\s-]?house', r'jackin', r'chicago[_\s-]?house', r'garage[_\s-]?house',
                  r'progressive[_\s-]?house', r'tropical'],
        'Drum_and_Bass': [r'drum[_\s-]?(and|&|n)[_\s-]?bass', r'dnb', r'd&b', r'd[_\s-]?n[_\s-]?b',
                          r'jungle', r'liquid', r'neuro', r'jump[_\s-]?up', r'breakcore'],
        'Dubstep': [r'dubstep', r'riddim', r'brostep', r'tearout', r'deep[_\s-]?dubstep',
                    r'melodic[_\s-]?dubstep', r'colour[_\s-]?bass', r'color[_\s-]?bass'],
        'Garage': [r'uk[_\s-]?garage', r'ukg', r'2[_\s-]?step', r'speed[_\s-]?garage',
                   r'bassline', r'4x4'],
        'Footwork': [r'footwork', r'juke', r'chicago[_\s-]?footwork', r'160[_\s-]?bpm'],
        'Trap': [r'trap', r'hip[_\s-]?hop', r'crunk', r'dirty[_\s-]?south', r'atlanta',
                 r'phonk', r'memphis', r'boom[_\s-]?bap', r'rap', r'beats'],
        'Drill': [r'drill', r'uk[_\s-]?drill', r'ny[_\s-]?drill', r'chicago[_\s-]?drill',
                  r'brooklyn[_\s-]?drill'],
        'Grime': [r'grime', r'uk[_\s-]?bass', r'8[_\s-]?bar', r'140[_\s-]?bpm'],
        'Trance': [r'trance', r'psytrance', r'psy[_\s-]?trance', r'progressive[_\s-]?trance',
                   r'uplifting', r'goa', r'hardstyle', r'hard[_\s-]?dance'],
        'Ambient': [r'ambient', r'experimental', r'downtempo', r'chill[_\s-]?out', r'idm',
                    r'electronica', r'soundscape', r'drone', r'atmospheric'],
        'Disco': [r'disco', r'nu[_\s-]?disco', r'funk', r'boogie', r'italo', r'cosmic'],
        'Synthwave': [r'synthwave', r'retrowave', r'outrun', r'vaporwave', r'80s',
                      r'synth[_\s-]?pop', r'electro[_\s-]?pop'],
        'Lo-Fi': [r'lo[_\s-]?fi', r'lofi', r'chill[_\s-]?hop', r'chillhop', r'jazzy',
                  r'dusty', r'tape', r'vinyl', r'bedroom'],
        'Pop': [r'pop', r'edm', r'mainstream', r'radio', r'commercial', r'dance[_\s-]?pop',
                r'future[_\s-]?pop', r'electro[_\s-]?pop'],
        'Drum_Machines': [r'808', r'909', r'707', r'727', r'606', r'303', r'cr[_\s-]?78',
                          r'tr[_\s-]?808', r'tr[_\s-]?909', r'linndrum', r'linn[_\s-]?drum',
                          r'dmx', r'oberheim', r'sp[_\s-]?1200', r'sp[_\s-]?12', r'mpc',
                          r'drum[_\s-]?machine', r'vintage[_\s-]?drum', r'analog[_\s-]?drum'],
    },
    'Live': {
        'Rock': [r'rock', r'indie', r'alternative', r'metal', r'grunge', r'hard[_\s-]?rock',
                 r'prog[_\s-]?rock', r'classic[_\s-]?rock', r'guitar[_\s-]?driven'],
        'Punk': [r'punk', r'post[_\s-]?punk', r'new[_\s-]?wave', r'no[_\s-]?wave',
                 r'hardcore', r'pop[_\s-]?punk', r'emo', r'screamo'],
        'Darkwave': [r'darkwave', r'dark[_\s-]?wave', r'coldwave', r'cold[_\s-]?wave',
                     r'goth', r'gothic', r'deathrock', r'ethereal', r'witch[_\s-]?house'],
        'Jazz': [r'jazz', r'fusion', r'bebop', r'swing', r'big[_\s-]?band', r'smooth[_\s-]?jazz',
                 r'acid[_\s-]?jazz', r'nu[_\s-]?jazz', r'broken[_\s-]?beat'],
        'Soul': [r'soul', r'r&b', r'rnb', r'r[_\s-]?and[_\s-]?b', r'motown', r'neo[_\s-]?soul',
                 r'gospel', r'rhythm[_\s-]?and[_\s-]?blues'],
        'Dub': [r'dub', r'reggae', r'roots', r'dancehall', r'ska', r'rocksteady',
                r'steppas', r'digital[_\s-]?dub'],
        'Blues': [r'blues', r'delta', r'chicago[_\s-]?blues', r'electric[_\s-]?blues',
                  r'slide[_\s-]?guitar', r'12[_\s-]?bar'],
        'Folk': [r'folk', r'country', r'americana', r'acoustic', r'singer[_\s-]?songwriter',
                 r'bluegrass', r'celtic', r'irish', r'appalachian'],
        'Classical': [r'classical', r'orchestral', r'cinematic', r'film[_\s-]?score',
                      r'strings', r'brass', r'woodwind', r'symphony', r'chamber',
                      r'epic', r'trailer', r'score'],
        'World': [r'world', r'ethnic', r'latin', r'african', r'afro', r'middle[_\s-]?eastern',
                  r'arabic', r'indian', r'asian', r'brazilian', r'cuban', r'flamenco',
                  r'tribal', r'percussion'],
        'Acoustic': [r'acoustic', r'live[_\s-]?drum', r'real[_\s-]?drum', r'studio[_\s-]?drum',
                     r'recorded', r'live[_\s-]?kit', r'natural', r'organic'],
    },
}

logger = logging.getLogger(__name__)


class SampleOrganizer:
    """Core logic for categorizing and symlinking samples."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.state = self._load_state()
        self._ensure_directories()

    def _ensure_directories(self):
        """Create all required directories."""
        dirs = [
            ORGANIZED_DIR / "All",
            # One-shots
            *[ORGANIZED_DIR / "One_Shots" / cat for cat in list(ONESHOT_CATEGORIES.keys()) + ["Other"]],
            # Loops
            *[ORGANIZED_DIR / "Loops" / cat for cat in list(LOOP_CATEGORIES.keys()) + ["Other"]],
            # Genres - Electronic
            *[ORGANIZED_DIR / "Genres" / "Electronic" / genre for genre in GENRE_CATEGORIES['Electronic'].keys()],
            # Genres - Live
            *[ORGANIZED_DIR / "Genres" / "Live" / genre for genre in GENRE_CATEGORIES['Live'].keys()],
            # Genres - Other (for samples that don't match any genre)
            ORGANIZED_DIR / "Genres" / "Other",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> dict:
        """Load previous state to track existing symlinks."""
        if STATE_FILE.exists():
            try:
                return json.loads(STATE_FILE.read_text())
            except json.JSONDecodeError:
                return {"files": {}}
        return {"files": {}}

    def _save_state(self):
        """Persist state to disk."""
        if not self.dry_run:
            STATE_FILE.write_text(json.dumps(self.state, indent=2))

    def process_file(self, source_path: Path) -> bool:
        """Process a single .wav file, creating symlinks."""
        if source_path.suffix.lower() != '.wav':
            return False

        if not source_path.exists():
            return False

        source_str = str(source_path)

        # Skip if already processed
        if source_str in self.state["files"]:
            return False

        # Determine if loop or one-shot
        is_loop = self._is_loop(source_str)

        # Get category
        category = self._categorize(source_str, is_loop)

        # Detect genres (can be multiple)
        genres = self._detect_genres(source_str)

        # Generate unique filename
        unique_name = self._generate_unique_name(source_path)

        if self.dry_run:
            type_folder = "Loops" if is_loop else "One_Shots"
            logger.info(f"[DRY RUN] Would create:")
            logger.info(f"  All/{unique_name}")
            logger.info(f"  {type_folder}/{category}/{unique_name}")
            if genres:
                for parent, genre in genres:
                    logger.info(f"  Genres/{parent}/{genre}/{unique_name}")
            else:
                logger.info(f"  Genres/Other/{unique_name}")
            return True

        # Create symlinks
        symlinks_created = []

        # 1. All/ folder
        all_link = ORGANIZED_DIR / "All" / unique_name
        self._create_link(source_path, all_link)
        symlinks_created.append(str(all_link))

        # 2. Categorized folder (One_Shots or Loops)
        if is_loop:
            cat_link = ORGANIZED_DIR / "Loops" / category / unique_name
        else:
            cat_link = ORGANIZED_DIR / "One_Shots" / category / unique_name

        self._create_link(source_path, cat_link)
        symlinks_created.append(str(cat_link))

        # 3. Genre folders (can be multiple)
        if genres:
            for parent, genre in genres:
                genre_link = ORGANIZED_DIR / "Genres" / parent / genre / unique_name
                self._create_link(source_path, genre_link)
                symlinks_created.append(str(genre_link))
        else:
            # No genre detected, put in Other
            genre_link = ORGANIZED_DIR / "Genres" / "Other" / unique_name
            self._create_link(source_path, genre_link)
            symlinks_created.append(str(genre_link))

        # Update state
        self.state["files"][source_str] = symlinks_created
        self._save_state()

        genre_str = ', '.join([g[1] for g in genres]) if genres else 'Other'
        logger.info(f"Processed: {source_path.name} -> {category} ({'Loop' if is_loop else 'One-Shot'}) [{genre_str}]")
        return True

    def remove_file(self, source_path: Path):
        """Remove symlinks when source file is deleted."""
        source_str = str(source_path)

        if source_str not in self.state["files"]:
            return

        if self.dry_run:
            logger.info(f"[DRY RUN] Would remove symlinks for: {source_path.name}")
            return

        for link_path in self.state["files"][source_str]:
            link = Path(link_path)
            if link.is_symlink():
                link.unlink()
                logger.info(f"Removed symlink: {link.name}")

        del self.state["files"][source_str]
        self._save_state()

    def _create_link(self, source: Path, link: Path):
        """Create hard link, handling existing files."""
        import os
        if link.exists() or link.is_symlink():
            link.unlink()
        os.link(source, link)

    def _is_loop(self, path: str) -> bool:
        """Determine if sample is a loop based on folder path and filename."""
        path_lower = path.lower()

        # Folder indicators (most reliable)
        loop_patterns = ['/loops/', '/loop/', '/drum_loops/', '/synth_loops/',
                        '/bass_loops/', '/percussion_loops/', '/vocal_loops/',
                        '/fx_loops/', '/melodic_loops/', '/music_loops/',
                        '/hat_loops/', '/kick_loops/', '/top_loops/']
        oneshot_patterns = ['/one_shots/', '/one-shots/', '/oneshots/', '/one_shot/',
                          '/hits/', '/drum_hits/', '/samples/', '/drum_one_shots/']

        for p in loop_patterns:
            if p in path_lower:
                return True
        for p in oneshot_patterns:
            if p in path_lower:
                return False

        # Filename indicators
        filename = Path(path).stem.lower()
        if '_loop' in filename or 'loop_' in filename:
            return True
        # BPM at start of filename usually indicates loop
        if re.search(r'^\d{2,3}_', filename):
            return True

        return False

    def _categorize(self, path: str, is_loop: bool) -> str:
        """Categorize sample by instrument/type."""
        path_obj = Path(path)

        # Build search text from multiple path components for better matching
        # Include: filename, parent folder, grandparent folder, and any folder after 'packs'
        parts_to_search = [path_obj.stem]  # filename without extension

        # Add parent folders (up to 4 levels, excluding common structural folders)
        skip_folders = {'sounds', 'packs', 'splice', 'samples', 'audio'}
        for parent in path_obj.parents:
            if parent.name.lower() not in skip_folders and parent.name:
                parts_to_search.append(parent.name)
            if len(parts_to_search) >= 5:
                break

        search_text = ' '.join(parts_to_search).lower()

        categories = LOOP_CATEGORIES if is_loop else ONESHOT_CATEGORIES

        for category, patterns in categories.items():
            for pattern in patterns:
                if re.search(pattern, search_text, re.IGNORECASE):
                    return category

        return 'Other'

    def _detect_genres(self, path: str) -> list:
        """Detect genres from pack name and path. Returns list of (parent, genre) tuples."""
        path_obj = Path(path)
        matched_genres = []

        # Build search text primarily from pack name and folder structure
        parts_to_search = []

        # Get pack name (most important for genre detection)
        try:
            parts = path_obj.parts
            idx = parts.index('packs')
            pack_name = parts[idx + 1]
            parts_to_search.append(pack_name)
            # Also include immediate subfolders of the pack
            if idx + 2 < len(parts):
                parts_to_search.append(parts[idx + 2])
        except (ValueError, IndexError):
            pass

        # Add some parent folders
        for parent in path_obj.parents:
            if parent.name and parent.name.lower() not in {'sounds', 'packs', 'splice', 'samples', 'audio', 'users', 'isaacfidler'}:
                parts_to_search.append(parent.name)
            if len(parts_to_search) >= 6:
                break

        search_text = ' '.join(parts_to_search).lower()

        # Check each genre category
        for parent_category, genres in GENRE_CATEGORIES.items():
            for genre, patterns in genres.items():
                for pattern in patterns:
                    if re.search(pattern, search_text, re.IGNORECASE):
                        genre_tuple = (parent_category, genre)
                        if genre_tuple not in matched_genres:
                            matched_genres.append(genre_tuple)
                        break  # Found a match for this genre, move to next genre

        return matched_genres

    def _generate_unique_name(self, source: Path) -> str:
        """Generate unique filename with pack prefix to avoid collisions."""
        parts = source.parts
        try:
            idx = parts.index('packs')
            pack_name = parts[idx + 1]
        except (ValueError, IndexError):
            pack_name = "Unknown"

        # Sanitize pack name
        safe_pack = re.sub(r'[^\w\-]', '_', pack_name)[:30]
        base_name = f"{safe_pack}__{source.stem}{source.suffix}"

        # Check All/ for collisions
        target = ORGANIZED_DIR / "All" / base_name
        if not target.exists() and str(source) not in self.state["files"]:
            return base_name

        # Check if this is the same file (already processed)
        if str(source) in self.state["files"]:
            existing_links = self.state["files"][str(source)]
            if existing_links:
                return Path(existing_links[0]).name

        # Add hash for collision
        content_hash = hashlib.md5(source.read_bytes()).hexdigest()[:8]
        return f"{safe_pack}__{source.stem}_{content_hash}{source.suffix}"

    def initial_sync(self):
        """Process all existing files."""
        logger.info("Starting initial sync...")
        count = 0
        total = 0

        wav_files = list(SPLICE_PACKS_DIR.rglob("*.wav"))
        total_files = len(wav_files)

        for i, wav_file in enumerate(wav_files):
            if self.process_file(wav_file):
                count += 1
            total += 1

            # Progress update every 100 files
            if total % 100 == 0:
                logger.info(f"Progress: {total}/{total_files} files scanned, {count} new files processed")

        logger.info(f"Initial sync complete: {count} new files processed out of {total_files} total")
        return count

    def resync(self):
        """Force reprocess all files by clearing state."""
        logger.info("Clearing state and removing all links...")

        # Remove all existing links (symlinks and hard links)
        for folder in ['All', 'One_Shots', 'Loops', 'Genres']:
            folder_path = ORGANIZED_DIR / folder
            if folder_path.exists():
                for item in folder_path.rglob('*'):
                    if item.is_file() or item.is_symlink():
                        item.unlink()

        # Clear state
        self.state = {"files": {}}
        self._save_state()

        # Reprocess
        return self.initial_sync()

    def show_stats(self):
        """Display categorization statistics."""
        stats = {
            'One_Shots': {},
            'Loops': {},
            'Genres_Electronic': {},
            'Genres_Live': {},
            'Genres_Other': 0,
            'Total': 0
        }

        for source_path, links in self.state["files"].items():
            stats['Total'] += 1
            for link in links:
                link_path = Path(link)
                parts = link_path.parts

                try:
                    org_idx = parts.index('Splice-Organized')
                    if org_idx + 1 < len(parts):
                        type_folder = parts[org_idx + 1]  # One_Shots, Loops, Genres, or All

                        if type_folder == 'One_Shots' and org_idx + 2 < len(parts):
                            category = parts[org_idx + 2]
                            stats['One_Shots'][category] = stats['One_Shots'].get(category, 0) + 1

                        elif type_folder == 'Loops' and org_idx + 2 < len(parts):
                            category = parts[org_idx + 2]
                            stats['Loops'][category] = stats['Loops'].get(category, 0) + 1

                        elif type_folder == 'Genres' and org_idx + 2 < len(parts):
                            parent = parts[org_idx + 2]  # Electronic, Live, or Other
                            if parent == 'Electronic' and org_idx + 3 < len(parts):
                                genre = parts[org_idx + 3]
                                stats['Genres_Electronic'][genre] = stats['Genres_Electronic'].get(genre, 0) + 1
                            elif parent == 'Live' and org_idx + 3 < len(parts):
                                genre = parts[org_idx + 3]
                                stats['Genres_Live'][genre] = stats['Genres_Live'].get(genre, 0) + 1
                            elif parent == 'Other':
                                stats['Genres_Other'] += 1

                except ValueError:
                    continue

        print("\n=== Splice Organizer Statistics ===\n")
        print(f"Total samples: {stats['Total']}\n")

        print("One-Shots:")
        for cat, count in sorted(stats['One_Shots'].items()):
            print(f"  {cat}: {count}")

        print("\nLoops:")
        for cat, count in sorted(stats['Loops'].items()):
            print(f"  {cat}: {count}")

        print("\nGenres - Electronic:")
        for genre, count in sorted(stats['Genres_Electronic'].items()):
            print(f"  {genre}: {count}")

        print("\nGenres - Live:")
        for genre, count in sorted(stats['Genres_Live'].items()):
            print(f"  {genre}: {count}")

        print(f"\nGenres - Other (untagged): {stats['Genres_Other']}")
        print()

    def validate(self):
        """Remove broken symlinks and clean up state."""
        logger.info("Validating symlinks...")
        removed = 0

        sources_to_remove = []

        for source_path, links in self.state["files"].items():
            source = Path(source_path)
            if not source.exists():
                # Source file was deleted, remove symlinks
                for link_path in links:
                    link = Path(link_path)
                    if link.is_symlink():
                        link.unlink()
                        removed += 1
                sources_to_remove.append(source_path)

        for source_path in sources_to_remove:
            del self.state["files"][source_path]

        self._save_state()
        logger.info(f"Validation complete: removed {removed} broken symlinks")


class SpliceEventHandler(FileSystemEventHandler):
    """Handle file system events from watchdog."""

    def __init__(self, organizer: SampleOrganizer):
        self.organizer = organizer

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() == '.wav':
            self.organizer.process_file(path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() == '.wav':
            self.organizer.remove_file(path)


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO

    # Ensure log directory exists
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )


def main():
    parser = argparse.ArgumentParser(
        description='Splice Sample Organizer - Create organized symlinks for your Splice samples'
    )
    parser.add_argument('--resync', action='store_true',
                       help='Force reprocess all files (clears existing symlinks)')
    parser.add_argument('--stats', action='store_true',
                       help='Show categorization statistics')
    parser.add_argument('--validate', action='store_true',
                       help='Remove broken symlinks and clean up state')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview changes without creating symlinks')
    parser.add_argument('--no-watch', action='store_true',
                       help='Run initial sync only, do not watch for changes')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose logging')

    args = parser.parse_args()

    setup_logging(args.verbose)

    if not SPLICE_PACKS_DIR.exists():
        logger.error(f"Splice packs directory not found: {SPLICE_PACKS_DIR}")
        sys.exit(1)

    organizer = SampleOrganizer(dry_run=args.dry_run)

    if args.stats:
        organizer.show_stats()
        return

    if args.validate:
        organizer.validate()
        return

    if args.resync:
        organizer.resync()
        if args.no_watch:
            return
    else:
        organizer.initial_sync()
        if args.no_watch:
            return

    # Start watching
    event_handler = SpliceEventHandler(organizer)
    observer = Observer()
    observer.schedule(event_handler, str(SPLICE_PACKS_DIR), recursive=True)
    observer.start()

    logger.info(f"Watching {SPLICE_PACKS_DIR} for changes... (Ctrl+C to stop)")

    try:
        while True:
            observer.join(timeout=1)
    except KeyboardInterrupt:
        logger.info("Stopping...")
        observer.stop()

    observer.join()


if __name__ == "__main__":
    main()
