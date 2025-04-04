from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
import os
import logging
from typing import List, Optional, Dict, Any
import uuid

from .worker.processor import process_youtube_video
from .utils.status_manager import StatusManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("clipod.log")
    ]
)
logger = logging.getLogger("clipod")

# Initialize the app
app = FastAPI(
    title="ClipOd API",
    description="API for generating TikTok clips from YouTube videos",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize status manager
status_manager = StatusManager()

# Models
class YouTubeURL(BaseModel):
    url: HttpUrl

class ClipInfo(BaseModel):
    id: str
    title: str
    start_time: float
    end_time: float
    duration: float
    file_path: str
    thumbnail_path: Optional[str] = None
    description: str

class ProcessStatus(BaseModel):
    job_id: str
    status: str
    current_step: str
    progress: float
    message: Optional[str] = None
    error: Optional[str] = None
    clips: Optional[List[ClipInfo]] = None

# Routes
@app.get("/")
async def root():
    return {"message": "Welcome to ClipOd API"}

@app.post("/process")
async def process_video(youtube_data: YouTubeURL, background_tasks: BackgroundTasks):
    """
    Start processing a YouTube video to generate TikTok clips
    """
    job_id = str(uuid.uuid4())
    logger.info(f"Starting job {job_id} for URL: {youtube_data.url}")
    
    # Initialize status
    status_manager.create_job(job_id)
    
    # Start processing in background
    background_tasks.add_task(
        process_youtube_video, 
        str(youtube_data.url), 
        job_id, 
        status_manager
    )
    
    return {"job_id": job_id, "message": "Processing started"}

@app.get("/status/{job_id}", response_model=ProcessStatus)
async def get_status(job_id: str):
    """
    Get the current status of a processing job
    """
    if not status_manager.job_exists(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    
    return status_manager.get_status(job_id)

@app.get("/clips")
async def get_clips():
    """
    Get a list of all generated clips
    """
    clips_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../clips"))
    
    if not os.path.exists(clips_dir):
        return {"clips": []}
    
    clips = []
    for job_id in os.listdir(clips_dir):
        job_dir = os.path.join(clips_dir, job_id)
        if os.path.isdir(job_dir):
            job_status = status_manager.get_status(job_id) if status_manager.job_exists(job_id) else None
            
            if job_status and job_status.clips:
                clips.extend(job_status.clips)
    
    return {"clips": clips}

@app.get("/clips/{job_id}")
async def get_job_clips(job_id: str):
    """
    Get clips for a specific job
    """
    if not status_manager.job_exists(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    
    status = status_manager.get_status(job_id)
    return {"clips": status.clips if status.clips else []}

@app.get("/download/{clip_id}")
async def download_clip(clip_id: str):
    """
    Download a specific clip
    """
    # Search for the clip in all job directories
    clips_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../clips"))
    
    for job_id in os.listdir(clips_dir):
        job_dir = os.path.join(clips_dir, job_id)
        if os.path.isdir(job_dir):
            for file in os.listdir(job_dir):
                if file.startswith(clip_id) and file.endswith(".mp4"):
                    file_path = os.path.join(job_dir, file)
                    return FileResponse(
                        path=file_path,
                        media_type="video/mp4",
                        filename=file
                    )
    
    raise HTTPException(status_code=404, detail="Clip not found")

# Serve static files (for development)
@app.get("/static/{file_path:path}")
async def get_static_file(file_path: str):
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../clips"))
    file_path = os.path.join(static_dir, file_path)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path)
