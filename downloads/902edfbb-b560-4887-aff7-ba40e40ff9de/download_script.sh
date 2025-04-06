#!/bin/bash
cd "/Users/timohaseloff/tikod/clipod/downloads/902edfbb-b560-4887-aff7-ba40e40ff9de"
echo "Starting download of https://youtu.be/M-mtdN6R3bQ at $(date)"
python3 -m yt_dlp -f "best[height<=720]" --ffmpeg-location "/opt/homebrew/bin/ffmpeg" -o "video.mp4" "https://youtu.be/M-mtdN6R3bQ" --verbose
echo "Download completed at $(date)"
