import {
  ChevronDown,
  ChevronsUpDown,
  GalleryVerticalEnd,
  Inbox,
  LayoutGrid,
  LifeBuoy,
  List,
  Search,
  Send,
  type LucideIcon,
} from 'lucide-react';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from '@/components/ui/sidebar';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

type NavItem = { icon: LucideIcon; label: string; active?: boolean };

const MAIN_NAV: NavItem[] = [
  { icon: Search, label: 'Search' },
  { icon: LayoutGrid, label: 'Projects' },
  { icon: List, label: 'Conversations', active: true },
  { icon: Inbox, label: 'Design system' },
];

const SECONDARY_NAV: NavItem[] = [
  { icon: LifeBuoy, label: 'Support' },
  { icon: Send, label: 'Feedback' },
];

function NavMenu({ items }: { items: NavItem[] }) {
  return (
    <SidebarMenu>
      {items.map((item) => (
        <SidebarMenuItem key={item.label}>
          <SidebarMenuButton isActive={item.active}>
            <item.icon />
            <span>{item.label}</span>
          </SidebarMenuButton>
        </SidebarMenuItem>
      ))}
    </SidebarMenu>
  );
}

export function AppSidebar() {
  return (
    <Sidebar collapsible="offcanvas" data-fig="main_menu">
      <SidebarHeader data-fig="Header">
        {/* project--swap */}
        <SidebarMenu data-fig="project--swap">
          <SidebarMenuItem>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton
                  size="lg"
                  className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                >
                  <div className="flex aspect-square size-8 items-center justify-center rounded-md bg-sidebar-primary text-sidebar-primary-foreground">
                    <GalleryVerticalEnd className="size-4" />
                  </div>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-semibold">My project</span>
                    <span className="truncate text-xs">Enterprise</span>
                  </div>
                  <ChevronsUpDown className="ml-auto size-4" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="start"
                className="w-[--radix-dropdown-menu-trigger-width]"
              >
                <DropdownMenuItem>My project</DropdownMenuItem>
                <DropdownMenuItem>Acme app</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>

        {/* conversation--swap */}
        <div data-fig="conversation--swap">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="flex h-9 w-full items-center overflow-hidden rounded-md border border-border bg-background"
              >
                <span className="flex flex-1 items-center justify-center border-r border-border px-4 py-2 text-sm font-medium text-foreground">
                  New conversation
                </span>
                <span className="flex size-9 shrink-0 items-center justify-center pl-2 pr-3">
                  <ChevronDown className="size-4" />
                </span>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem>New conversation</DropdownMenuItem>
              <DropdownMenuItem>Recent thread</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup data-fig="main_menu--options">
          <SidebarGroupContent>
            <NavMenu items={MAIN_NAV} />
          </SidebarGroupContent>
          <SidebarGroupLabel data-fig="title--conversations">
            Conversations
          </SidebarGroupLabel>
        </SidebarGroup>

        <SidebarGroup data-fig="menu-down--fill" className="mt-auto">
          <SidebarGroupContent>
            <NavMenu items={SECONDARY_NAV} />
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter data-fig="footer">
        <SidebarMenu>
          <SidebarMenuItem data-fig="user">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton
                  size="lg"
                  className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                >
                  <Avatar className="size-8 rounded-md">
                    <AvatarFallback className="rounded-md bg-[#efdbff] text-[#531dab]">
                      SC
                    </AvatarFallback>
                  </Avatar>
                  <div className="grid flex-1 text-left text-sm leading-tight">
                    <span className="truncate font-semibold">Shadcn</span>
                    <span className="truncate text-xs">m@example.com</span>
                  </div>
                  <ChevronsUpDown className="ml-auto size-4" />
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                className="w-[--radix-dropdown-menu-trigger-width]"
              >
                <DropdownMenuItem>Account</DropdownMenuItem>
                <DropdownMenuItem>Log out</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
