import { Download } from 'lucide-react'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '../components/ui/card'
import { formatDuration } from '../lib/utils'
import { VideoClip } from '../types'

interface VideoClipGridProps {
  clips: VideoClip[]
}

export function VideoClipGrid({ clips }: VideoClipGridProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {clips.map((clip) => (
        <VideoClipCard key={clip.id} clip={clip} />
      ))}
    </div>
  )
}

interface VideoClipCardProps {
  clip: VideoClip
}

function VideoClipCard({ clip }: VideoClipCardProps) {
  const handleDownload = () => {
    window.open(`/api/download/${clip.id}`, '_blank')
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="p-4">
        <CardTitle className="text-lg truncate">{clip.title}</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="relative aspect-[9/16] bg-muted">
          <video 
            src={`/api/static/${clip.file_path.split('/').slice(-2).join('/')}`}
            className="w-full h-full object-contain"
            controls
          />
        </div>
      </CardContent>
      <CardFooter className="p-4 flex justify-between items-center">
        <div className="text-sm text-muted-foreground">
          {formatDuration(clip.duration)}
        </div>
        <Button 
          size="sm" 
          variant="outline" 
          onClick={handleDownload}
        >
          <Download className="w-4 h-4 mr-2" />
          Download
        </Button>
      </CardFooter>
    </Card>
  )
}
