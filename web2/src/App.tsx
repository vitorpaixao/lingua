import { AppSidebar } from '@/components/AppSidebar';
import { StageHeader } from '@/components/StageHeader';
import { ChatPanel } from '@/components/ChatPanel';
import { PreviewPane } from '@/components/PreviewPane';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';

/**
 * The single workspace screen from Figma node 17:178 (Lingua-shadcnui).
 * shadcn shell everywhere except the chat, which is real Ant Design X.
 */
export default function App() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset data-fig="stage" className="h-screen min-w-0">
        <StageHeader />
        <div
          data-fig="stage--project_content"
          className="flex min-h-0 flex-1 items-stretch"
        >
          <ChatPanel />
          <PreviewPane />
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
