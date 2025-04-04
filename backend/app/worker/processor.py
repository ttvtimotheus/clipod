import os
import logging
import subprocess
import json
import time
import uuid
import re
from typing import List, Dict, Any, Optional
import tempfile
import shutil

import yt_dlp
import openai
import ffmpeg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger("clipod.processor")

# Get OpenAI API key from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning("OpenAI API key not found in environment variables")

# Base directories
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
TRANSCRIPTS_DIR = os.path.join(BASE_DIR, "transcripts")
CLIPS_DIR = os.path.join(BASE_DIR, "clips")

# Ensure directories exist
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
os.makedirs(CLIPS_DIR, exist_ok=True)

# Whisper model size
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "medium")

async def process_youtube_video(url: str, job_id: str, status_manager):
    """
    Process a YouTube video to generate TikTok clips
    
    Steps:
    1. Download the video
    2. Transcribe the audio
    3. Identify highlights using GPT-4o
    4. Generate clips
    """
    try:
        # Create job directory
        job_dir = os.path.join(CLIPS_DIR, job_id)
        os.makedirs(job_dir, exist_ok=True)
        
        # Step 1: Download the video
        status_manager.update_status(
            job_id,
            status="processing",
            current_step="downloading",
            progress=5.0,
            message="Downloading YouTube video"
        )
        
        video_path = await download_youtube_video(url, job_id)
        
        # Step 2: Transcribe the video
        status_manager.update_status(
            job_id,
            current_step="transcribing",
            progress=25.0,
            message="Transcribing video audio"
        )
        
        transcript_path, srt_path = await transcribe_video(video_path, job_id)
        
        # Step 3: Identify highlights
        status_manager.update_status(
            job_id,
            current_step="analyzing",
            progress=50.0,
            message="Analyzing transcript for highlights"
        )
        
        highlights = await identify_highlights(transcript_path, job_id)
        
        # Step 4: Generate clips
        status_manager.update_status(
            job_id,
            current_step="generating_clips",
            progress=75.0,
            message=f"Generating {len(highlights)} clips"
        )
        
        clips = await generate_clips(video_path, srt_path, highlights, job_id)
        
        # Update status with generated clips
        for clip in clips:
            status_manager.add_clip(job_id, clip)
        
        # Mark job as completed
        status_manager.mark_completed(job_id)
        
        # Save status to disk
        status_manager.save_to_disk()
        
        return clips
        
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}", exc_info=True)
        status_manager.mark_failed(job_id, str(e))
        status_manager.save_to_disk()
        raise e

async def download_youtube_video(url: str, job_id: str) -> str:
    """
    Download a YouTube video using yt-dlp
    """
    logger.info(f"Downloading video from {url}")
    
    # Create download directory for this job
    job_download_dir = os.path.join(DOWNLOADS_DIR, job_id)
    os.makedirs(job_download_dir, exist_ok=True)
    
    # yt-dlp options
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(job_download_dir, '%(title)s.%(ext)s'),
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
        'ignoreerrors': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get('title', 'video')
            video_path = os.path.join(job_download_dir, f"{video_title}.mp4")
            
            # Check if the file exists, if not, try to find it
            if not os.path.exists(video_path):
                for file in os.listdir(job_download_dir):
                    if file.endswith(".mp4"):
                        video_path = os.path.join(job_download_dir, file)
                        break
            
            logger.info(f"Downloaded video to {video_path}")
            return video_path
    except Exception as e:
        logger.error(f"Error downloading video: {str(e)}", exc_info=True)
        raise Exception(f"Failed to download video: {str(e)}")

async def transcribe_video(video_path: str, job_id: str) -> tuple:
    """
    Transcribe video using Whisper
    """
    logger.info(f"Transcribing video {video_path}")
    
    # Create transcript directory for this job
    job_transcript_dir = os.path.join(TRANSCRIPTS_DIR, job_id)
    os.makedirs(job_transcript_dir, exist_ok=True)
    
    # Base filename without extension
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    
    # Output paths
    transcript_path = os.path.join(job_transcript_dir, f"{base_name}.txt")
    srt_path = os.path.join(job_transcript_dir, f"{base_name}.srt")
    
    try:
        # Run whisper command
        cmd = [
            "python", "-m", "whisper", 
            video_path,
            "--model", WHISPER_MODEL,
            "--output_dir", job_transcript_dir,
            "--output_format", "srt,txt"
        ]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Whisper transcription failed: {stderr}")
            raise Exception(f"Transcription failed: {stderr}")
        
        logger.info(f"Transcription completed: {transcript_path}")
        
        # Ensure the files exist
        if not os.path.exists(transcript_path) or not os.path.exists(srt_path):
            # Try to find the files with different names
            for file in os.listdir(job_transcript_dir):
                if file.endswith(".txt"):
                    transcript_path = os.path.join(job_transcript_dir, file)
                elif file.endswith(".srt"):
                    srt_path = os.path.join(job_transcript_dir, file)
        
        return transcript_path, srt_path
        
    except Exception as e:
        logger.error(f"Error transcribing video: {str(e)}", exc_info=True)
        raise Exception(f"Failed to transcribe video: {str(e)}")

async def identify_highlights(transcript_path: str, job_id: str) -> List[Dict[str, Any]]:
    """
    Identify highlights in the transcript using GPT-4o
    """
    logger.info(f"Identifying highlights from transcript {transcript_path}")
    
    try:
        # Read transcript
        with open(transcript_path, 'r', encoding='utf-8') as f:
            transcript_text = f.read()
        
        # Initialize OpenAI client
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        
        # Prepare prompt for GPT-4o
        prompt = f"""
        You are an expert video editor tasked with finding the most engaging highlights from a YouTube video transcript.
        
        Your goal is to identify 3-5 self-contained segments that would make compelling TikTok clips (15-60 seconds each).
        
        For each highlight:
        1. Find a segment with a clear beginning and end
        2. Ensure it contains interesting, entertaining, or informative content
        3. The segment should make sense on its own without additional context
        4. Prefer segments with emotional moments, key insights, funny interactions, or surprising revelations
        
        Here's the transcript:
        
        {transcript_text}
        
        For each highlight, provide:
        1. Start time (in format HH:MM:SS or MM:SS)
        2. End time (in format HH:MM:SS or MM:SS)
        3. A catchy title for the clip (max 50 characters)
        4. A brief description of why this segment is compelling (1-2 sentences)
        
        Format your response as a JSON array with the following structure:
        [
            {{
                "start_time": "MM:SS",
                "end_time": "MM:SS",
                "title": "Catchy Title Here",
                "description": "Brief description of why this is compelling"
            }},
            ...
        ]
        
        Only include the JSON array in your response, nothing else.
        """
        
        # Call GPT-4o API
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that identifies engaging video highlights."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        # Extract and parse the response
        highlights_json = response.choices[0].message.content.strip()
        
        # Clean up the JSON string if needed (remove markdown code blocks, etc.)
        highlights_json = re.sub(r'^```json\s*', '', highlights_json)
        highlights_json = re.sub(r'\s*```$', '', highlights_json)
        
        highlights = json.loads(highlights_json)
        
        # Convert time strings to seconds
        for highlight in highlights:
            highlight["start_seconds"] = time_to_seconds(highlight["start_time"])
            highlight["end_seconds"] = time_to_seconds(highlight["end_time"])
            highlight["duration"] = highlight["end_seconds"] - highlight["start_seconds"]
        
        logger.info(f"Identified {len(highlights)} highlights")
        return highlights
        
    except Exception as e:
        logger.error(f"Error identifying highlights: {str(e)}", exc_info=True)
        raise Exception(f"Failed to identify highlights: {str(e)}")

async def generate_clips(video_path: str, srt_path: str, highlights: List[Dict[str, Any]], job_id: str) -> List[Dict[str, Any]]:
    """
    Generate video clips using ffmpeg
    """
    logger.info(f"Generating {len(highlights)} clips from {video_path}")
    
    # Create clips directory for this job
    job_clips_dir = os.path.join(CLIPS_DIR, job_id)
    os.makedirs(job_clips_dir, exist_ok=True)
    
    generated_clips = []
    
    try:
        for i, highlight in enumerate(highlights):
            # Generate a unique ID for this clip
            clip_id = str(uuid.uuid4())[:8]
            
            # Sanitize title for filename
            safe_title = re.sub(r'[^\w\s-]', '', highlight["title"]).strip().replace(' ', '_')
            
            # Output path
            clip_filename = f"{clip_id}_{safe_title}.mp4"
            clip_path = os.path.join(job_clips_dir, clip_filename)
            
            # Extract the relevant part of the SRT file
            temp_srt = await extract_srt_segment(
                srt_path, 
                highlight["start_seconds"], 
                highlight["end_seconds"],
                os.path.join(job_clips_dir, f"temp_{clip_id}.srt")
            )
            
            # Generate the clip with ffmpeg
            start_time = highlight["start_seconds"]
            duration = highlight["duration"]
            
            # Run ffmpeg to create 9:16 clip with subtitles
            try:
                # First pass: extract the clip
                (
                    ffmpeg
                    .input(video_path, ss=start_time, t=duration)
                    .output(os.path.join(job_clips_dir, f"temp_{clip_id}.mp4"), c="copy")
                    .run(quiet=True, overwrite_output=True)
                )
                
                # Second pass: convert to 9:16 with centered zoom and add subtitles
                (
                    ffmpeg
                    .input(os.path.join(job_clips_dir, f"temp_{clip_id}.mp4"))
                    .filter('crop', 'in_w', 'in_w*16/9', '(in_w-out_w)/2', '(in_h-out_h)/2')
                    .filter('scale', -1, 1920)
                    .filter('subtitles', temp_srt, force_style='FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H80000000,BorderStyle=4')
                    .output(clip_path)
                    .run(quiet=True, overwrite_output=True)
                )
                
                # Clean up temporary files
                os.remove(os.path.join(job_clips_dir, f"temp_{clip_id}.mp4"))
                os.remove(temp_srt)
                
                # Add clip info to the list
                clip_info = {
                    "id": clip_id,
                    "title": highlight["title"],
                    "start_time": highlight["start_seconds"],
                    "end_time": highlight["end_seconds"],
                    "duration": highlight["duration"],
                    "file_path": clip_path,
                    "description": highlight["description"]
                }
                
                generated_clips.append(clip_info)
                logger.info(f"Generated clip: {clip_path}")
                
            except ffmpeg.Error as e:
                logger.error(f"Error generating clip {i+1}: {e.stderr.decode() if e.stderr else str(e)}")
                continue
            
    except Exception as e:
        logger.error(f"Error generating clips: {str(e)}", exc_info=True)
        raise Exception(f"Failed to generate clips: {str(e)}")
    
    return generated_clips

async def extract_srt_segment(srt_path: str, start_seconds: float, end_seconds: float, output_path: str) -> str:
    """
    Extract a segment from an SRT file based on start and end times
    """
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            srt_content = f.read()
        
        # Parse SRT content
        subtitle_blocks = re.split(r'\n\s*\n', srt_content.strip())
        
        # Extract relevant subtitles
        relevant_blocks = []
        new_index = 1
        
        for block in subtitle_blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue
            
            # Parse time range
            time_line = lines[1]
            time_match = re.match(r'(\d+:\d+:\d+,\d+)\s*-->\s*(\d+:\d+:\d+,\d+)', time_line)
            
            if not time_match:
                continue
            
            sub_start = time_to_seconds(time_match.group(1).replace(',', '.'))
            sub_end = time_to_seconds(time_match.group(2).replace(',', '.'))
            
            # Check if this subtitle is within our clip range
            if sub_end < start_seconds or sub_start > end_seconds:
                continue
            
            # Adjust the timing
            adjusted_start = max(0, sub_start - start_seconds)
            adjusted_end = min(end_seconds - start_seconds, sub_end - start_seconds)
            
            # Format the new time
            new_start_str = seconds_to_srt_time(adjusted_start)
            new_end_str = seconds_to_srt_time(adjusted_end)
            
            # Create new block
            new_block = f"{new_index}\n{new_start_str} --> {new_end_str}\n" + '\n'.join(lines[2:])
            relevant_blocks.append(new_block)
            new_index += 1
        
        # Write the new SRT file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(relevant_blocks))
        
        return output_path
    
    except Exception as e:
        logger.error(f"Error extracting SRT segment: {str(e)}", exc_info=True)
        # Create an empty SRT file as fallback
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('')
        return output_path

def time_to_seconds(time_str: str) -> float:
    """
    Convert a time string (HH:MM:SS or MM:SS) to seconds
    """
    parts = time_str.replace(',', '.').split(':')
    
    if len(parts) == 3:  # HH:MM:SS
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    elif len(parts) == 2:  # MM:SS
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    else:
        try:
            return float(time_str)
        except ValueError:
            return 0.0

def seconds_to_srt_time(seconds: float) -> str:
    """
    Convert seconds to SRT time format (HH:MM:SS,mmm)
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    milliseconds = int((seconds - int(seconds)) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"
