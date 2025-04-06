#!/bin/bash
cd "/Users/timohaseloff/tikod/clipod/downloads/fb39b54a-4685-425b-a198-fa5a15a12e15"
echo "Starting download of https://youtu.be/M-mtdN6R3bQ at $(date)"
python3 -m yt_dlp -f "best[height<=720]" --ffmpeg-location "/opt/homebrew/bin/ffmpeg" -o "video.mp4" "https://youtu.be/M-mtdN6R3bQ" --verbose
echo "Download completed at $(date)"
