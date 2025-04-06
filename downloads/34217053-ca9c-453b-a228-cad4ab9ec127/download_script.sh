#!/bin/bash
cd "/Users/timohaseloff/tikod/clipod/downloads/34217053-ca9c-453b-a228-cad4ab9ec127"
echo "Starting download of https://youtu.be/M-mtdN6R3bQ at $(date)"
python3 -m yt_dlp -f "best[height<=720]" --ffmpeg-location "/opt/homebrew/bin/ffmpeg" -o "video.mp4" "https://youtu.be/M-mtdN6R3bQ" --verbose
echo "Download completed at $(date)"
