'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { MessageSquare, FileText, CalendarCheck, ArrowRight, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useApiToken, apiFetchJson } from '@/lib/client-api';
import { formatDate } from '@/lib/utils';

const quickActions = [
  { href: '/chat', label: '開始新對話', icon: MessageSquare, description: '向 AI 助理提問，獲取知識庫資訊' },
  { href: '/docgen', label: '生成文件', icon: FileText, description: '使用 AI 生成提案、報告、會議記錄等' },
  { href: '/meetings', label: '上傳會議錄音', icon: CalendarCheck, description: '轉寫會議錄音並生成摘要' },
];

export default function DashboardPage() {
  const [conversations, setConversations] = useState<any[]>([]);
  const [meetings, setMeetings] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const token = useApiToken();

  useEffect(() => {
    if (!token) return;
    Promise.all([
      apiFetchJson<any[]>('/api/v1/conversations', token).catch(() => []),
      apiFetchJson<any[]>('/api/v1/meetings', token).catch(() => []),
    ]).then(([convs, meets]) => {
      setConversations((convs || []).slice(0, 5));
      setMeetings((meets || []).slice(0, 5));
    }).finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">儀表板</h1>
        <p className="text-muted-foreground mt-1">歡迎使用仁愛堂 AI 文件與知識平台</p>
      </div>

      <div>
        <h2 className="text-lg font-semibold mb-3">快速操作</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {quickActions.map((action) => (
            <Link key={action.href} href={action.href}>
              <Card className="h-full transition-shadow hover:shadow-md cursor-pointer">
                <CardHeader className="flex flex-row items-center gap-4 pb-2">
                  <div className="rounded-lg bg-primary/10 p-2">
                    <action.icon className="h-5 w-5 text-primary" />
                  </div>
                  <CardTitle className="text-base">{action.label}</CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription>{action.description}</CardDescription>
                  <div className="flex items-center gap-1 text-sm text-primary mt-3">
                    開始使用 <ArrowRight className="h-3 w-3" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">最近對話</CardTitle>
            <CardDescription>您最近的 AI 對話記錄</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> :
              conversations.length === 0 ? <p className="text-sm text-muted-foreground">尚未有對話記錄</p> :
              <div className="space-y-2">
                {conversations.map((c: any) => (
                  <Link key={c.id} href="/chat" className="flex items-center justify-between rounded-md p-2 text-sm hover:bg-muted transition-colors">
                    <span className="truncate"><MessageSquare className="inline h-3 w-3 mr-2 text-muted-foreground" />{c.title || '未命名對話'}</span>
                    <span className="text-xs text-muted-foreground shrink-0 ml-2">{formatDate(c.updated_at)}</span>
                  </Link>
                ))}
              </div>
            }
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">最近會議</CardTitle>
            <CardDescription>最近上傳的會議錄音</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> :
              meetings.length === 0 ? <p className="text-sm text-muted-foreground">尚未有會議記錄</p> :
              <div className="space-y-2">
                {meetings.map((m: any) => (
                  <Link key={m.id} href="/meetings" className="flex items-center justify-between rounded-md p-2 text-sm hover:bg-muted transition-colors">
                    <span className="truncate"><CalendarCheck className="inline h-3 w-3 mr-2 text-muted-foreground" />{m.title}</span>
                    <span className="text-xs text-muted-foreground shrink-0 ml-2">{formatDate(m.created_at)}</span>
                  </Link>
                ))}
              </div>
            }
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
