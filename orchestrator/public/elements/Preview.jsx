import { Button } from "@/components/ui/button"
import { RefreshCw, ExternalLink } from "lucide-react"

export default function Preview() {
  const refresh = () => {
    const iframe = document.getElementById("lingua-preview")
    if (iframe) iframe.src = iframe.src
  }

  const openNewTab = () => {
    window.open("http://localhost:3000", "_blank")
  }

  return (
    <div className="flex flex-col h-full w-full">
      <div className="flex items-center justify-between px-3 py-2 border-b bg-muted/50">
        <span className="text-xs text-muted-foreground">localhost:3000</span>
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={refresh}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={openNewTab}>
            <ExternalLink className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
      <div className="flex-1">
        <iframe
          id="lingua-preview"
          src="http://localhost:3000"
          className="w-full h-full border-none block"
          title="Live preview"
        />
      </div>
    </div>
  )
}
