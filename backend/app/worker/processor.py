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
import httpx
import asyncio

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

# Get ffmpeg path from environment
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
logger.info(f"Using ffmpeg path: {FFMPEG_PATH}")

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
    Process a YouTube video by downloading, transcribing, and generating clips
    """
    logger.info(f"Starting processing job {job_id} for URL: {url}")
    logger.info(f"Using directories: Downloads={DOWNLOADS_DIR}, Transcripts={TRANSCRIPTS_DIR}, Clips={CLIPS_DIR}")
    
    try:
        # Step 1: Download the video
        logger.info(f"Downloading video from {url}")
        status_manager.update_status(job_id=job_id, status="processing", current_step="downloading", progress=0, message="Downloading video")
        
        # Directly implement video download here to avoid issues with yt-dlp library
        try:
            # Create job directory in downloads
            job_download_dir = os.path.join(DOWNLOADS_DIR, job_id)
            os.makedirs(job_download_dir, exist_ok=True)
            
            # Output file path
            output_file = os.path.join(job_download_dir, "video.mp4")
            
            # Create a shell script to download the video
            script_path = os.path.join(job_download_dir, "download_script.sh")
            with open(script_path, "w") as f:
                f.write(f"""#!/bin/bash
cd "{job_download_dir}"
echo "Starting download of {url} at $(date)"
python3 -m yt_dlp -f "best[height<=720]" --ffmpeg-location "{FFMPEG_PATH}" -o "video.mp4" "{url}" --verbose
echo "Download completed at $(date)"
""")
            
            # Make the script executable
            os.chmod(script_path, 0o755)
            
            # Run the script as a separate process
            logger.info(f"Running download script: {script_path}")
            
            # Use a shorter timeout for testing
            # In production, you might want to use a longer timeout or no timeout
            timeout_seconds = 600  # 10 minutes
            
            # Start the process
            process = subprocess.Popen(
                ["/bin/bash", script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=job_download_dir,
                text=True,
                bufsize=1
            )
            
            # Create a log file for the output
            log_file_path = os.path.join(job_download_dir, "download_log.txt")
            with open(log_file_path, 'w') as log_file:
                log_file.write(f"Download started at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_file.write(f"Command: /bin/bash {script_path}\n\n")
                
                # Use a non-blocking approach to read output while the process is running
                try:
                    start_time = time.time()
                    while process.poll() is None:
                        # Check if we've exceeded the timeout
                        if time.time() - start_time > timeout_seconds:
                            process.kill()
                            log_file.write(f"\nProcess killed after {timeout_seconds} seconds timeout\n")
                            raise TimeoutError(f"Download process timed out after {timeout_seconds} seconds")
                        
                        # Read output without blocking
                        stdout_line = process.stdout.readline()
                        if stdout_line:
                            log_file.write(f"STDOUT: {stdout_line}")
                            logger.debug(f"Download output: {stdout_line.strip()}")
                        
                        stderr_line = process.stderr.readline()
                        if stderr_line:
                            log_file.write(f"STDERR: {stderr_line}")
                            logger.debug(f"Download error: {stderr_line.strip()}")
                        
                        # Sleep briefly to avoid CPU spinning
                        if not stdout_line and not stderr_line:
                            await asyncio.sleep(0.1)
                    
                    # Process has finished, get any remaining output
                    stdout, stderr = process.communicate()
                    if stdout:
                        log_file.write(f"STDOUT (final): {stdout}\n")
                    if stderr:
                        log_file.write(f"STDERR (final): {stderr}\n")
                    
                    log_file.write(f"\nProcess completed with return code {process.returncode}\n")
                    
                    if process.returncode != 0:
                        raise Exception(f"Download script failed with return code {process.returncode}")
                
                except Exception as e:
                    log_file.write(f"\nError during download: {str(e)}\n")
                    raise
            
            # Check if file exists
            if not os.path.exists(output_file):
                # Try to find any video file in the directory
                video_files = [f for f in os.listdir(job_download_dir) if f.endswith(('.mp4', '.webm', '.mkv'))]
                if video_files:
                    # Use the first video file found
                    output_file = os.path.join(job_download_dir, video_files[0])
                    logger.info(f"Found video file: {output_file}")
                else:
                    # Check the log file for clues
                    with open(log_file_path, 'r') as log_file:
                        log_content = log_file.read()
                        logger.error(f"No video file found. Log content: {log_content[:1000]}...")
                    
                    raise Exception("No video file found after download. Check the log file for details.")
            
            video_path = output_file
            logger.info(f"Successfully downloaded video to {video_path}")
            
        except Exception as e:
            logger.error(f"Error downloading video: {str(e)}", exc_info=True)
            status_manager.update_status(
                job_id=job_id,
                status="failed",
                current_step="downloading",
                progress=0,
                message="Failed to download video",
                error=f"Download error: {str(e)}"
            )
            return
        
        # Step 2: Transcribe the video
        logger.info(f"Transcribing video {video_path}")
        status_manager.update_status(job_id=job_id, status="processing", current_step="transcribing", progress=20, message="Transcribing video")
        
        try:
            transcript_path, srt_path = await transcribe_video(video_path, job_id)
            logger.info(f"Transcription completed: {transcript_path}")
        except Exception as e:
            logger.error(f"Error transcribing video: {str(e)}", exc_info=True)
            status_manager.update_status(
                job_id=job_id,
                status="failed",
                current_step="transcribing",
                progress=20,
                message="Failed to transcribe video",
                error=f"Transcription error: {str(e)}"
            )
            return
        
        # Step 3: Identify highlights
        logger.info(f"Identifying highlights from transcript")
        status_manager.update_status(job_id=job_id, status="processing", current_step="analyzing", progress=40, message="Identifying highlights")
        
        try:
            highlights = await identify_highlights(transcript_path, job_id)
            logger.info(f"Identified {len(highlights)} highlights")
        except Exception as e:
            logger.error(f"Error identifying highlights: {str(e)}", exc_info=True)
            status_manager.update_status(
                job_id=job_id,
                status="failed",
                current_step="analyzing",
                progress=40,
                message="Failed to identify highlights",
                error=f"Analysis error: {str(e)}"
            )
            return
        
        # Step 4: Generate clips
        logger.info(f"Generating clips from highlights")
        status_manager.update_status(job_id=job_id, status="processing", current_step="generating_clips", progress=60, message="Generating clips")
        
        try:
            clips = await generate_clips(video_path, srt_path, highlights, job_id)
            logger.info(f"Generated {len(clips)} clips")
        except Exception as e:
            logger.error(f"Error generating clips: {str(e)}", exc_info=True)
            status_manager.update_status(
                job_id=job_id,
                status="failed",
                current_step="generating_clips",
                progress=60,
                message="Failed to generate clips",
                error=f"Clip generation error: {str(e)}"
            )
            return
        
        # Update status to completed
        status_manager.update_status(
            job_id=job_id,
            status="completed",
            current_step="completed",
            progress=100,
            message="Processing completed",
            clips=clips
        )
        
        logger.info(f"Processing completed for job {job_id}")
        
    except Exception as e:
        logger.error(f"Error processing video: {str(e)}", exc_info=True)
        status_manager.update_status(
            job_id=job_id,
            status="failed",
            current_step="processing",
            progress=0,
            message="Processing failed",
            error=f"Processing error: {str(e)}"
        )

async def download_youtube_video(url: str, job_id: str) -> str:
    """
    Download a YouTube video using direct HTTP request
    """
    try:
        # Create job directory in downloads
        job_download_dir = os.path.join(DOWNLOADS_DIR, job_id)
        os.makedirs(job_download_dir, exist_ok=True)
        
        # Simple output file path
        output_file = os.path.join(job_download_dir, "video.mp4")
        
        # Test if ffmpeg works directly
        logger.info(f"Testing ffmpeg at path: {FFMPEG_PATH}")
        try:
            result = subprocess.run([FFMPEG_PATH, "-version"], capture_output=True, text=True, check=True)
            logger.info(f"FFmpeg test result: {result.stdout[:100]}...")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg test failed with return code {e.returncode}: {e.stderr}")
            raise Exception(f"FFmpeg test failed: {e.stderr}")
        except Exception as e:
            logger.error(f"Error testing ffmpeg: {str(e)}")
            raise Exception(f"Error testing ffmpeg: {str(e)}")
        
        # Try a completely different approach - use youtube-dl as a separate process
        # This avoids the Python library issues
        logger.info(f"Downloading video from {url} using youtube-dl as separate process")
        
        # Create a temporary script to run youtube-dl
        script_path = os.path.join(job_download_dir, "download_script.sh")
        with open(script_path, "w") as f:
            f.write(f"""#!/bin/bash
cd "{job_download_dir}"
python3 -m yt_dlp -f "best[height<=720]" --ffmpeg-location "{FFMPEG_PATH}" -o "video.mp4" "{url}"
""")
        
        # Make the script executable
        os.chmod(script_path, 0o755)
        
        # Run the script in a separate process
        logger.info(f"Running download script: {script_path}")
        process = subprocess.Popen(
            ["/bin/bash", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=job_download_dir
        )
        
        # Wait for the process to complete with a timeout
        try:
            stdout, stderr = process.communicate(timeout=300)
            if process.returncode != 0:
                error_message = stderr.decode('utf-8')
                logger.error(f"Download script failed: {error_message}")
                raise Exception(f"Download script failed: {error_message}")
            else:
                logger.info(f"Download script completed successfully")
        except subprocess.TimeoutExpired:
            process.kill()
            logger.error("Download script timed out after 300 seconds")
            raise Exception("Download timed out after 300 seconds")
        
        # Check if file exists
        if not os.path.exists(output_file):
            # Try to find any video file in the directory
            video_files = [f for f in os.listdir(job_download_dir) if f.endswith(('.mp4', '.webm', '.mkv'))]
            if video_files:
                # Use the first video file found
                output_file = os.path.join(job_download_dir, video_files[0])
                logger.info(f"Found video file: {output_file}")
            else:
                logger.error(f"No video file found in {job_download_dir}")
                raise Exception(f"Failed to download video: No video file found")
        
        logger.info(f"Successfully downloaded video to {output_file}")
        return output_file
    
    except Exception as e:
        logger.error(f"Error downloading video: {str(e)}", exc_info=True)
        raise Exception(f"Failed to download video: {str(e)}")

async def download_youtube_video_alternative(url: str, job_id: str) -> str:
    """
    Download a YouTube video using direct HTTP request with httpx
    """
    try:
        # Create job directory in downloads
        job_download_dir = os.path.join(DOWNLOADS_DIR, job_id)
        os.makedirs(job_download_dir, exist_ok=True)
        
        # Simple output file path
        output_file = os.path.join(job_download_dir, "video.mp4")
        
        # Use httpx to download the video
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True, stream=True)
            response.raise_for_status()
            
            with open(output_file, 'wb') as f:
                num_bytes_downloaded = response.num_bytes_downloaded
                total_bytes = int(response.headers['Content-Length'])
                for chunk in response.iter_bytes():
                    f.write(chunk)
                    num_bytes_downloaded += len(chunk)
                    logger.info(f"Downloading video: {num_bytes_downloaded / total_bytes * 100:.2f}%")
        
        logger.info(f"Successfully downloaded video to {output_file}")
        return output_file
    
    except Exception as e:
        logger.error(f"Error downloading video: {str(e)}", exc_info=True)
        raise Exception(f"Failed to download video: {str(e)}")

async def transcribe_video(video_path: str, job_id: str) -> tuple:
    """
    Transcribe a video using OpenAI's Whisper model
    Returns the path to the transcript file and SRT file
    """
    logger.info(f"Transcribing video {video_path} for job {job_id}")
    
    # Create transcripts directory if it doesn't exist
    job_transcript_dir = os.path.join(TRANSCRIPTS_DIR, job_id)
    os.makedirs(job_transcript_dir, exist_ok=True)
    
    transcript_path = os.path.join(job_transcript_dir, "transcript.json")
    srt_path = os.path.join(job_transcript_dir, "transcript.srt")
    
    try:
        # Temporary fix for SSL certificate issues on macOS
        import ssl
        ssl._create_default_https_context = ssl._create_unverified_context
        
        import whisper
        
        # Load the Whisper model
        model_size = os.environ.get("WHISPER_MODEL", "medium")
        logger.info(f"Loading Whisper model: {model_size}")
        model = whisper.load_model(model_size)
        
        # Transcribe the video
        logger.info(f"Starting transcription of {video_path}")
        result = model.transcribe(video_path)
        
        # Save the transcript to a JSON file
        with open(transcript_path, "w") as f:
            json.dump(result, f, indent=2)
        
        # Convert the transcript to SRT format
        segments = result["segments"]
        with open(srt_path, "w") as f:
            for i, segment in enumerate(segments):
                start_time = segment["start"]
                end_time = segment["end"]
                text = segment["text"].strip()
                
                # Format times as HH:MM:SS,mmm
                start_formatted = format_time(start_time)
                end_formatted = format_time(end_time)
                
                # Write the SRT entry
                f.write(f"{i+1}\n")
                f.write(f"{start_formatted} --> {end_formatted}\n")
                f.write(f"{text}\n\n")
        
        logger.info(f"Transcription completed: {transcript_path}")
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

def format_time(seconds: float) -> str:
    """
    Format a timestamp in seconds to HH:MM:SS format
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    
    return f"{hours:02d}:{minutes:02d}:{seconds:05.2f}"
