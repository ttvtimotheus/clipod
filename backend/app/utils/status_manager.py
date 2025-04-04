from typing import Dict, List, Optional, Any
import time
import threading
import json
import os
import logging

logger = logging.getLogger("clipod.status_manager")

class StatusManager:
    """
    Manages the status of processing jobs
    """
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        
    def create_job(self, job_id: str) -> None:
        """
        Initialize a new job with default status
        """
        with self._lock:
            self.jobs[job_id] = {
                "job_id": job_id,
                "status": "initializing",
                "current_step": "starting",
                "progress": 0.0,
                "message": "Job initialized",
                "error": None,
                "clips": [],
                "start_time": time.time(),
                "update_time": time.time()
            }
        logger.info(f"Created job {job_id}")
    
    def update_status(self, job_id: str, **kwargs) -> None:
        """
        Update the status of a job
        """
        if not self.job_exists(job_id):
            logger.warning(f"Attempted to update non-existent job {job_id}")
            return
        
        with self._lock:
            for key, value in kwargs.items():
                if key in self.jobs[job_id]:
                    self.jobs[job_id][key] = value
            
            self.jobs[job_id]["update_time"] = time.time()
        
        logger.debug(f"Updated job {job_id}: {kwargs}")
    
    def add_clip(self, job_id: str, clip_info: dict) -> None:
        """
        Add a clip to the job's clips list
        """
        if not self.job_exists(job_id):
            logger.warning(f"Attempted to add clip to non-existent job {job_id}")
            return
        
        with self._lock:
            if "clips" not in self.jobs[job_id]:
                self.jobs[job_id]["clips"] = []
            
            self.jobs[job_id]["clips"].append(clip_info)
        
        logger.info(f"Added clip to job {job_id}: {clip_info.get('title', 'Untitled')}")
    
    def get_status(self, job_id: str) -> dict:
        """
        Get the current status of a job
        """
        if not self.job_exists(job_id):
            logger.warning(f"Attempted to get status of non-existent job {job_id}")
            return {}
        
        with self._lock:
            return self.jobs[job_id].copy()
    
    def job_exists(self, job_id: str) -> bool:
        """
        Check if a job exists
        """
        return job_id in self.jobs
    
    def mark_completed(self, job_id: str) -> None:
        """
        Mark a job as completed
        """
        self.update_status(
            job_id,
            status="completed",
            current_step="finished",
            progress=100.0,
            message="Processing completed successfully"
        )
        logger.info(f"Job {job_id} completed")
    
    def mark_failed(self, job_id: str, error_message: str) -> None:
        """
        Mark a job as failed
        """
        self.update_status(
            job_id,
            status="failed",
            message=f"Processing failed: {error_message}",
            error=error_message
        )
        logger.error(f"Job {job_id} failed: {error_message}")
    
    def save_to_disk(self, base_dir: str = None) -> None:
        """
        Save all job statuses to disk
        """
        if base_dir is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        
        status_dir = os.path.join(base_dir, "status")
        os.makedirs(status_dir, exist_ok=True)
        
        with self._lock:
            for job_id, status in self.jobs.items():
                file_path = os.path.join(status_dir, f"{job_id}.json")
                with open(file_path, 'w') as f:
                    json.dump(status, f, indent=2)
        
        logger.debug(f"Saved {len(self.jobs)} job statuses to disk")
    
    def load_from_disk(self, base_dir: str = None) -> None:
        """
        Load all job statuses from disk
        """
        if base_dir is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        
        status_dir = os.path.join(base_dir, "status")
        if not os.path.exists(status_dir):
            logger.warning(f"Status directory {status_dir} does not exist")
            return
        
        with self._lock:
            for filename in os.listdir(status_dir):
                if filename.endswith(".json"):
                    file_path = os.path.join(status_dir, filename)
                    try:
                        with open(file_path, 'r') as f:
                            status = json.load(f)
                            job_id = status.get("job_id")
                            if job_id:
                                self.jobs[job_id] = status
                    except Exception as e:
                        logger.error(f"Failed to load status from {file_path}: {e}")
        
        logger.info(f"Loaded {len(self.jobs)} job statuses from disk")
