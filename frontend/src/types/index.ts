export interface VideoClip {
  id: string
  title: string
  start_time: number
  end_time: number
  duration: number
  file_path: string
  thumbnail_path?: string
  description: string
}

export interface ProcessStatus {
  job_id: string
  status: 'initializing' | 'processing' | 'completed' | 'failed'
  current_step: string
  progress: number
  message?: string
  error?: string
  clips?: VideoClip[]
}
