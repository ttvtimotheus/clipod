#!/bin/bash

# ClipOd Startup Script
echo "Starting ClipOd application..."

# Create necessary directories if they don't exist
mkdir -p downloads clips transcripts status

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is required but not installed."
    exit 1
fi

# Check if Node.js is installed
if ! command -v npm &> /dev/null; then
    echo "Error: npm is required but not installed."
    exit 1
fi

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "Warning: ffmpeg is required for video processing but not found."
    echo "Please install ffmpeg to use video processing features."
fi

# Check if the OpenAI API key is set
if [ ! -f backend/.env ]; then
    echo "Warning: .env file not found in backend directory."
    echo "Please create a .env file with your OpenAI API key."
    echo "Example: OPENAI_API_KEY=your_api_key_here"
fi

# Start the backend server in the background
echo "Starting backend server..."
cd backend
python3 server.py &
BACKEND_PID=$!
cd ..

# Install frontend dependencies if needed
echo "Checking frontend dependencies..."
cd frontend
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Start the frontend
echo "Starting frontend..."
npm run dev &
FRONTEND_PID=$!
cd ..

echo "ClipOd is running!"
echo "Backend server: http://localhost:8000"
echo "Frontend application: http://localhost:5173"
echo "Press Ctrl+C to stop all services"

# Function to handle shutdown
function cleanup {
    echo "Shutting down ClipOd..."
    kill $BACKEND_PID
    kill $FRONTEND_PID
    echo "Services stopped."
    exit 0
}

# Register the cleanup function for SIGINT (Ctrl+C)
trap cleanup SIGINT

# Keep the script running
wait
