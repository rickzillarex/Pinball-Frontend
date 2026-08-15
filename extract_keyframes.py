#!/usr/bin/env python3
"""
Extract keyframes from MP4 files.
Called by the Table Manager web app during folder scanning.
Requires: ffmpeg installed and in PATH
"""
import json
import subprocess
import sys
from pathlib import Path

def extract_keyframe(mp4_path, output_jpg_path):
    """Extract first keyframe from mp4 and save as jpg."""
    try:
        cmd = [
            'ffmpeg',
            '-i', str(mp4_path),
            '-vf', "select=eq(pict_type\\,I)",
            '-vframes', '1',
            '-y',  # overwrite without asking
            str(output_jpg_path)
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=30)
        return True
    except subprocess.TimeoutExpired:
        print(f"Timeout extracting keyframe from {mp4_path}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error on {mp4_path}: {e.stderr.decode()}")
        return False
    except FileNotFoundError:
        print("FFmpeg not found. Install it from https://ffmpeg.org/download.html")
        return False

def main():
    """
    Called with: python extract_keyframes.py /path/to/media/folder
    Scans folder for .mp4 files and extracts keyframes as .jpg
    """
    if len(sys.argv) < 2:
        print("Usage: python extract_keyframes.py /path/to/media/folder")
        sys.exit(1)

    media_folder = Path(sys.argv[1])
    if not media_folder.is_dir():
        print(f"Error: {media_folder} is not a directory")
        sys.exit(1)

    results = {
        "extracted": [],
        "skipped": [],
        "errors": []
    }

    # Find all .mp4 files
    for mp4_file in sorted(media_folder.glob("*.mp4")):
        jpg_file = mp4_file.with_suffix(".jpg")

        # Skip if jpg already exists
        if jpg_file.exists():
            results["skipped"].append(mp4_file.name)
            continue

        print(f"Extracting keyframe from {mp4_file.name}...", end=" ", flush=True)
        if extract_keyframe(mp4_file, jpg_file):
            results["extracted"].append({
                "mp4": mp4_file.name,
                "jpg": jpg_file.name
            })
            print("✓")
        else:
            results["errors"].append(mp4_file.name)
            print("✗")

    # Output results as JSON for the web app to read
    print(json.dumps(results))

if __name__ == "__main__":
    main()
