import { useState } from 'react'
import { Youtube, Scissors, Download, Clock, Menu, X, Settings, Home, Video, History } from 'lucide-react'
import { Button } from './components/ui/button'
import { Input } from './components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card'
import { Progress } from './components/ui/progress'
import { Separator } from './components/ui/separator'
import { useToast } from './components/ui/use-toast'
import { VideoClipGrid } from './components/video-clip-grid'
import { ProcessStatus, VideoClip } from './types'

function App() {
  const [youtubeUrl, setYoutubeUrl] = useState<string>('')
  const [isProcessing, setIsProcessing] = useState<boolean>(false)
  const [status, setStatus] = useState<ProcessStatus | null>(null)
  const [clips, setClips] = useState<VideoClip[]>([])
  const [sidebarOpen, setSidebarOpen] = useState<boolean>(true)
  const { toast } = useToast()

  // Function to start processing a YouTube video
  const handleProcessVideo = async () => {
    if (!youtubeUrl) {
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'Please enter a YouTube URL',
      })
      return
    }

    try {
      setIsProcessing(true)
      const response = await fetch('/api/process', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url: youtubeUrl }),
      })

      if (!response.ok) {
        throw new Error('Failed to start processing')
      }

      const data = await response.json()
      
      toast({
        title: 'Processing Started',
        description: 'Your video is now being processed.',
      })

      // Start polling for status updates
      pollStatus(data.job_id)
    } catch (error) {
      console.error('Error starting process:', error)
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'Failed to start processing',
      })
      setIsProcessing(false)
    }
  }

  // Function to poll for status updates
  const pollStatus = async (jobId: string) => {
    const interval = setInterval(async () => {
      try {
        const response = await fetch(`/api/status/${jobId}`)
        if (!response.ok) {
          throw new Error('Failed to get status')
        }

        const statusData = await response.json()
        setStatus(statusData)

        // If processing is complete, fetch the clips
        if (statusData.status === 'completed') {
          clearInterval(interval)
          setIsProcessing(false)
          fetchClips(jobId)
        } else if (statusData.status === 'failed') {
          clearInterval(interval)
          setIsProcessing(false)
          toast({
            variant: 'destructive',
            title: 'Processing Failed',
            description: statusData.error || 'An unknown error occurred',
          })
        }
      } catch (error) {
        console.error('Error polling status:', error)
      }
    }, 2000) // Poll every 2 seconds

    // Cleanup function
    return () => clearInterval(interval)
  }

  // Function to fetch clips for a job
  const fetchClips = async (jobId: string) => {
    try {
      const response = await fetch(`/api/clips/${jobId}`)
      if (!response.ok) {
        throw new Error('Failed to fetch clips')
      }

      const data = await response.json()
      setClips(data.clips || [])
      
      toast({
        title: 'Processing Complete',
        description: `Generated ${data.clips?.length || 0} clips successfully.`,
      })
    } catch (error) {
      console.error('Error fetching clips:', error)
      toast({
        variant: 'destructive',
        title: 'Error',
        description: 'Failed to fetch clips',
      })
    }
  }

  // Calculate the current step description
  const getCurrentStepDescription = () => {
    if (!status) return 'Waiting to start...'
    
    switch (status.current_step) {
      case 'downloading':
        return 'Downloading YouTube video...'
      case 'transcribing':
        return 'Transcribing audio with Whisper...'
      case 'analyzing':
        return 'Analyzing transcript with GPT-4o...'
      case 'generating_clips':
        return 'Generating TikTok clips with ffmpeg...'
      case 'finished':
        return 'Processing complete!'
      default:
        return status.current_step
    }
  }

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'w-64' : 'w-20'} bg-muted/40 border-r border-border transition-all duration-300 hidden md:block`}>
        <div className="flex flex-col h-full">
          <div className="p-4 flex items-center justify-between">
            <div className={`flex items-center ${!sidebarOpen && 'justify-center w-full'}`}>
              <Youtube className="h-6 w-6 text-red-500" />
              {sidebarOpen && <span className="ml-2 font-semibold text-lg">ClipOd</span>}
            </div>
            <Button 
              variant="ghost" 
              size="icon" 
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className={!sidebarOpen ? 'hidden' : ''}
            >
              <Menu className="h-5 w-5" />
            </Button>
          </div>
          <Separator />
          <nav className="flex-1 p-2">
            <div className="space-y-1">
              {[
                { icon: <Home className="h-5 w-5" />, label: 'Dashboard', active: true },
                { icon: <Video className="h-5 w-5" />, label: 'My Clips' },
                { icon: <History className="h-5 w-5" />, label: 'History' },
                { icon: <Settings className="h-5 w-5" />, label: 'Settings' },
              ].map((item, i) => (
                <Button 
                  key={i} 
                  variant={item.active ? "secondary" : "ghost"} 
                  className={`w-full justify-${sidebarOpen ? 'start' : 'center'} mb-1`}
                >
                  {item.icon}
                  {sidebarOpen && <span className="ml-2">{item.label}</span>}
                </Button>
              ))}
            </div>
          </nav>
          <div className="p-4">
            <div className="text-xs text-muted-foreground text-center">
              {sidebarOpen ? 'ClipOd v1.0.0' : 'v1.0'}
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Header */}
      <div className="md:hidden fixed top-0 left-0 right-0 h-16 bg-background border-b border-border z-10 flex items-center justify-between px-4">
        <div className="flex items-center">
          <Youtube className="h-6 w-6 text-red-500" />
          <span className="ml-2 font-semibold text-lg">ClipOd</span>
        </div>
        <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(!sidebarOpen)}>
          {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </Button>
      </div>

      {/* Mobile Sidebar */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 bg-background z-50 pt-16">
          <nav className="p-4">
            <div className="space-y-2">
              {[
                { icon: <Home className="h-5 w-5" />, label: 'Dashboard', active: true },
                { icon: <Video className="h-5 w-5" />, label: 'My Clips' },
                { icon: <History className="h-5 w-5" />, label: 'History' },
                { icon: <Settings className="h-5 w-5" />, label: 'Settings' },
              ].map((item, i) => (
                <Button 
                  key={i} 
                  variant={item.active ? "secondary" : "ghost"} 
                  className="w-full justify-start mb-1"
                >
                  {item.icon}
                  <span className="ml-2">{item.label}</span>
                </Button>
              ))}
            </div>
          </nav>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 overflow-auto">
        <div className="container py-6 md:py-10 px-4 max-w-6xl mx-auto md:mt-0 mt-16">
          {/* Page Header */}
          <header className="mb-8">
            <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
            <p className="text-muted-foreground mt-1">
              Create TikTok-ready clips from YouTube videos
            </p>
          </header>

          {/* Main Content Grid */}
          <div className="grid gap-6">
            {/* Input Card */}
            <Card>
              <CardHeader>
                <CardTitle>Process a YouTube Video</CardTitle>
                <CardDescription>
                  Enter a YouTube URL to analyze and create TikTok-ready clips
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-6">
                  <div className="flex flex-col md:flex-row items-start md:items-center gap-3">
                    <div className="flex-1 w-full">
                      <Input
                        placeholder="https://www.youtube.com/watch?v=..."
                        value={youtubeUrl}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setYoutubeUrl(e.target.value)}
                        disabled={isProcessing}
                        className="h-10"
                      />
                    </div>
                    <Button 
                      onClick={handleProcessVideo} 
                      disabled={isProcessing || !youtubeUrl}
                      className="w-full md:w-auto"
                    >
                      {isProcessing ? 'Processing...' : 'Analyze Video'}
                    </Button>
                  </div>

                  {isProcessing && status && (
                    <div className="space-y-3">
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-medium">
                          {getCurrentStepDescription()}
                        </span>
                        <span className="text-sm font-medium">{Math.round(status.progress)}%</span>
                      </div>
                      <Progress value={status.progress} />
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Process Steps */}
            {!clips.length && !isProcessing && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {[
                  { icon: <Youtube className="h-5 w-5" />, title: "Download", desc: "Download YouTube video" },
                  { icon: <Clock className="h-5 w-5" />, title: "Transcribe", desc: "Generate transcript with Whisper" },
                  { icon: <Scissors className="h-5 w-5" />, title: "Analyze", desc: "Find highlights with GPT-4o" },
                  { icon: <Download className="h-5 w-5" />, title: "Generate", desc: "Create TikTok-ready clips" },
                ].map((step, i) => (
                  <Card key={i}>
                    <CardHeader className="pb-2">
                      <div className="flex items-center space-x-2">
                        <div className="p-2 bg-muted rounded-md">
                          {step.icon}
                        </div>
                        <CardTitle className="text-base">{step.title}</CardTitle>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground">{step.desc}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}

            {/* Generated Clips */}
            {clips.length > 0 && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-2xl font-bold">Generated Clips</h2>
                  <div className="text-sm px-3 py-1 rounded-full bg-muted">
                    {clips.length} clip{clips.length !== 1 ? 's' : ''} generated
                  </div>
                </div>
                <Separator />
                <VideoClipGrid clips={clips} />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
