#!/bin/bash
cd "/Users/timohaseloff/tikod/clipod/downloads/b9ccd8f4-bc0a-455b-ada1-f12385a45a6f"
python3 -m yt_dlp -f "best[height<=720]" --ffmpeg-location "/opt/homebrew/bin/ffmpeg" -o "video.mp4" "https://youtu.be/M-mtdN6R3bQ"
