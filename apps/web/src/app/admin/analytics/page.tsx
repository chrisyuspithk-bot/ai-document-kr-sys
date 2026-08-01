'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BarChart3, Users, FileText, MessageSquare, Loader2 } from 'lucide-react';
import { useApiToken, apiFetchJson } from '@/lib/client-api';

export default function AdminAnalyticsPage() {
  const [stats, setStats] = useState({ users: 0, kbs: 0, totalDocs: 0, genDocs: 0 });
  const [loading, setLoading] = useState(true);
  const token = useApiToken();

  useEffect(() => {
    if (!token) return;
    async function load() {
      try {
        const [users, kbs, genDocs] = await Promise.all([
          apiFetchJson<any[]>('/api/v1/users', token).catch(() => []),
          apiFetchJson<any[]>('/api/v1/knowledge-bases', token).catch(() => []),
          apiFetchJson<any[]>('/api/v1/gen-documents', token).catch(() => []),
        ]);
        const totalDocs = (kbs as any[]).reduce((sum: number, kb: any) => sum + (kb.document_count || 0), 0);
        setStats({ users: (users as any[]).length, kbs: (kbs as any[]).length, totalDocs, genDocs: (genDocs as any[]).length });
      } catch {}
      finally { setLoading(false); }
    }
    load();
  }, [token]);

  const items = [
    { label: '用戶總數', value: stats.users, icon: Users },
    { label: '知識庫數量', value: stats.kbs, icon: BarChart3 },
    { label: '文件總數', value: stats.totalDocs, icon: FileText },
    { label: 'AI 生成文件', value: stats.genDocs, icon: MessageSquare },
  ];

  return (
    <div className="space-y-6">
      <div><h1 className="text-2xl font-bold tracking-tight">系統分析</h1><p className="text-muted-foreground text-sm">系統使用狀況和指標</p></div>
      {loading ? <div className="text-center py-12"><Loader2 className="mx-auto h-6 w-6 animate-spin" /></div> :
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {items.map((s) => (
            <Card key={s.label}>
              <CardHeader className="flex flex-row items-center justify-between pb-2"><CardTitle className="text-sm font-medium">{s.label}</CardTitle><s.icon className="h-4 w-4 text-muted-foreground" /></CardHeader>
              <CardContent><div className="text-2xl font-bold">{s.value}</div></CardContent>
            </Card>
          ))}
        </div>
      }
    </div>
  );
}
