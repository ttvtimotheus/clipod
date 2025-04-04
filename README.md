# ClipOd

ClipOd is a modern web application that automatically creates TikTok-ready clips from YouTube videos. It analyzes videos, identifies highlights using AI, adds subtitles, and generates vertical (9:16) format clips for social media sharing.

## Features

- **YouTube Video Processing**: Download videos from YouTube using a simple URL
- **Automatic Transcription**: Transcribe videos using OpenAI's Whisper AI (locally)
- **Intelligent Highlight Detection**: Use GPT-4o to identify the most engaging parts of videos
- **Automatic Clip Generation**: Convert highlights to vertical (9:16) TikTok-ready video clips
- **Subtitle Integration**: Add hardcoded subtitles to clips for better engagement
- **Modern UI**: Clean, responsive interface built with React, TypeScript and shadcn/ui

## Tech Stack

### Frontend
- React with TypeScript
- Vite for build tooling
- Tailwind CSS for styling
- shadcn/ui for UI components

### Backend
- FastAPI (Python)
- yt-dlp for YouTube video downloading
- Whisper for local transcription
- OpenAI GPT-4o API for highlight detection
- ffmpeg for video processing

## Project Structure

```
clipod/
├── backend/               # FastAPI backend
│   ├── app/               # Main application code
│   │   ├── utils/         # Utility functions
│   │   └── worker/        # Processing worker
│   ├── requirements.txt   # Python dependencies
│   └── .env               # Environment variables
├── frontend/              # React frontend
│   ├── src/               # Source code
│   │   ├── components/    # React components
│   │   ├── lib/           # Utility functions
│   │   └── types/         # TypeScript types
│   └── package.json       # Node.js dependencies
├── downloads/             # Downloaded YouTube videos
├── clips/                 # Generated clips
└── transcripts/           # Video transcripts
```

## Getting Started

### Prerequisites

- Node.js (v16+)
- Python (v3.9+)
- ffmpeg

### Installation

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/clipod.git
cd clipod
```

2. **Set up the backend**

```bash
cd backend
pip install -r requirements.txt
# Copy and edit the .env file with your OpenAI API key
cp .env.example .env
```

3. **Set up the frontend**

```bash
cd frontend
npm install
```

### Running the Application

1. **Start the backend server**

```bash
cd backend
python server.py
```

2. **Start the frontend development server**

```bash
cd frontend
npm run dev
```

3. **Access the application**

Open your browser and navigate to `http://localhost:5173`

## Usage

1. Enter a YouTube URL in the input field
2. Click "Analyze Video" to start the processing
3. Wait for the processing to complete (you can track the progress)
4. View, play, and download the generated clips

## Environment Variables

Create a `.env` file in the backend directory with the following variables:

```
OPENAI_API_KEY=your_openai_api_key_here
WHISPER_MODEL=medium
PORT=8000
HOST=0.0.0.0
DEBUG=True
FRONTEND_URL=http://localhost:5173
```

## Future Enhancements

- TikTok upload automation
- User authentication system
- Custom clip editing
- Batch processing of multiple videos
- Compilation clip creation

## License

This project is open source and available under the MIT License.cd backend && pip install -r requirements.txt
cd frontend && npm install