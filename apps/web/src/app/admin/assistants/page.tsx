'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Plus, Loader2, Bot } from 'lucide-react';
import { formatDate } from '@/lib/utils';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function AdminAssistantsPage() {
  const [assistants, setAssistants] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') || '' : '';

  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE}/api/v1/assistants`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : []).then(setAssistants).catch(() => {}).finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between"><div><h1 className="text-2xl font-bold tracking-tight">AI 助理配置</h1><p className="text-muted-foreground text-sm">管理 AI 助理的提示詞、模型和知識庫範圍</p></div><Button><Plus className="mr-2 h-4 w-4" />建立助理</Button></div>
      {loading ? <div className="text-center py-12"><Loader2 className="mx-auto h-6 w-6 animate-spin" /></div> :
        <Card><CardContent className="p-0"><Table><TableHeader><TableRow><TableHead>名稱</TableHead><TableHead>模型</TableHead><TableHead>模式</TableHead><TableHead>狀態</TableHead><TableHead>建立日期</TableHead></TableRow></TableHeader>
          <TableBody>{assistants.length === 0 ? <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">暫無 AI 助理</TableCell></TableRow> :
            assistants.map((a: any) => (
              <TableRow key={a.id}><TableCell className="font-medium"><div className="flex items-center gap-2"><Bot className="h-4 w-4 text-primary" />{a.name}</div></TableCell>
                <TableCell className="text-sm">{a.model || '預設'}</TableCell>
                <TableCell><Badge variant={a.web_enabled ? 'default' : 'secondary'} className="text-xs">{a.web_enabled ? '網絡搜尋' : '僅內部'}</Badge></TableCell>
                <TableCell><Badge variant={a.is_public ? 'success' : 'outline'} className="text-xs">{a.is_public ? '公開' : '內部'}</Badge></TableCell>
                <TableCell className="text-muted-foreground text-sm">{formatDate(a.created_at)}</TableCell></TableRow>
            ))}</TableBody></Table></CardContent></Card>}
    </div>
  );
}
