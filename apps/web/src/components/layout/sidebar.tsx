'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard, MessageSquare, FileText, CalendarCheck,
  BookOpen, Users, Bot, ShieldCheck, Key, BarChart3,
  Settings, ChevronLeft, ChevronRight, ChevronDown, FolderCog,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { useState, useEffect } from 'react';

interface NavItem {
  href: string;
  label: string;
  icon: React.ElementType;
  adminOnly?: boolean;
}

const mainNav: NavItem[] = [
  { href: '/dashboard', label: '儀表板', icon: LayoutDashboard },
  { href: '/chat', label: 'AI 對話', icon: MessageSquare },
  { href: '/docgen', label: '文件生成', icon: FileText },
  { href: '/meetings', label: '會議中心', icon: CalendarCheck },
];

const adminNav: NavItem[] = [
  { href: '/admin/kb', label: '知識庫管理', icon: BookOpen },
  { href: '/admin/documents', label: '文件管理', icon: FileText },
  { href: '/admin/users', label: '用戶管理', icon: Users },
  { href: '/admin/assistants', label: 'AI 助理', icon: Bot },
  { href: '/admin/audit', label: '審計日誌', icon: ShieldCheck },
  { href: '/admin/api-keys', label: 'API 密鑰', icon: Key },
  { href: '/admin/analytics', label: '系統分析', icon: BarChart3 },
];

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const isAdminActive = adminNav.some((item) => pathname.startsWith(item.href));
  const [adminOpen, setAdminOpen] = useState(false);

  useEffect(() => {
    if (isAdminActive) setAdminOpen(true);
  }, [isAdminActive]);

  return (
    <aside className={cn(
      'flex flex-col border-r bg-card transition-all duration-300',
      collapsed ? 'w-16' : 'w-64'
    )}>
      <div className="flex h-14 items-center border-b px-4">
        {!collapsed && (
          <Link href="/dashboard" className="flex items-center gap-2 font-semibold">
            <BookOpen className="h-5 w-5 text-primary" />
            <span className="text-sm">AI 文件與知識平台</span>
          </Link>
        )}
        <Button
          variant="ghost"
          size="icon"
          className={cn('ml-auto h-8 w-8', collapsed && 'mx-auto')}
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>

      <ScrollArea className="flex-1 py-2">
        <nav className="grid gap-1 px-2">
          {mainNav.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground',
                pathname === item.href || pathname.startsWith(item.href + '/')
                  ? 'bg-accent text-accent-foreground'
                  : 'text-muted-foreground',
                collapsed && 'justify-center px-2'
              )}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </Link>
          ))}
        </nav>

        <Separator className="my-3" />

        {/* Collapsible admin section */}
        <button
          onClick={() => { if (!collapsed) setAdminOpen(!adminOpen); }}
          className={cn(
            'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground',
            isAdminActive ? 'text-accent-foreground' : 'text-muted-foreground',
            collapsed && 'justify-center px-2'
          )}
        >
          <FolderCog className="h-4 w-4 shrink-0" />
          {!collapsed && (
            <>
              <span className="flex-1 text-left">管理後台</span>
              <ChevronDown className={cn('h-3 w-3 transition-transform', adminOpen && 'rotate-180')} />
            </>
          )}
        </button>

        {(adminOpen || collapsed) && (
          <nav className="grid gap-1 px-2">
            {adminNav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground',
                  pathname.startsWith(item.href)
                    ? 'bg-accent text-accent-foreground'
                    : 'text-muted-foreground',
                  collapsed && 'justify-center px-2',
                  !collapsed && 'pl-8'
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            ))}
          </nav>
        )}
      </ScrollArea>

      <div className="border-t p-2">
        <Link
          href="/settings"
          className={cn(
            'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground',
            collapsed && 'justify-center px-2'
          )}
        >
          <Settings className="h-4 w-4 shrink-0" />
          {!collapsed && <span>設定</span>}
        </Link>
      </div>
    </aside>
  );
}
