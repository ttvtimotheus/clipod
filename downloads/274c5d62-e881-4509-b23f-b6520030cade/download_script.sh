#!/bin/bash
cd "/Users/timohaseloff/tikod/clipod/downloads/274c5d62-e881-4509-b23f-b6520030cade"
python3 -m yt_dlp -f "best[height<=720]" --ffmpeg-location "/opt/homebrew/bin/ffmpeg" -o "video.mp4" "https://youtu.be/M-mtdN6R3bQ"
