import {
  GitBranch,
  Moon,
  MousePointerClick,
  Send,
  Sun,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { SidebarTrigger } from '@/components/ui/sidebar';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useTheme } from '@/lib/theme';

export function StageHeader() {
  const { mode, toggle } = useTheme();
  return (
    <header
      data-fig="stage--header"
      className="flex h-12 w-full shrink-0 items-center border-b border-border"
    >
      <div className="flex flex-1 items-center gap-2 px-4">
        {/* left */}
        <div data-fig="left" className="flex flex-1 items-center gap-2">
          <SidebarTrigger data-fig="show-hide__main_menu" className="size-7" />
          <Separator
            data-fig="separator"
            orientation="vertical"
            className="h-4"
          />
          <Select defaultValue="enterprise">
            <SelectTrigger className="h-9 w-[180px]">
              <SelectValue placeholder="Select" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="enterprise">Enterprise</SelectItem>
              <SelectItem value="startup">Startup</SelectItem>
            </SelectContent>
          </Select>
          <Badge data-fig="git-branch" variant="success">
            <GitBranch className="size-3" />
            main - 2 ahead
          </Badge>
        </div>

        {/* right */}
        <div data-fig="right" className="flex flex-1 items-center justify-end gap-2">
          <Button
            variant="ghost"
            size="icon"
            className="size-8"
            onClick={toggle}
            aria-label="Toggle theme"
          >
            {mode === 'dark' ? (
              <Sun className="size-4" />
            ) : (
              <Moon className="size-4" />
            )}
          </Button>
          <Button variant="outline" size="sm" className="h-8 gap-1.5">
            <MousePointerClick className="size-4" />
            Select
          </Button>
          <Button
            size="sm"
            className="h-8 gap-1.5 bg-[#0958d9] text-white hover:bg-[#0958d9]/90"
          >
            <Send className="size-4" />
            Publish
          </Button>
        </div>
      </div>
    </header>
  );
}
