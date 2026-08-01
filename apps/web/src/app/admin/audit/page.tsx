'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Download, Loader2 } from 'lucide-react';
import { formatDate } from '@/lib/utils';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function AdminAuditPage() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') || '' : '';

  useEffect(() => {
    if (!token) return;
    fetch(`${API_BASE}/api/v1/audit-logs?limit=100`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => r.ok ? r.json() : []).then(setLogs).catch(() => {}).finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between"><div><h1 className="text-2xl font-bold tracking-tight">審計日誌</h1><p className="text-muted-foreground text-sm">檢視所有系統操作記錄</p></div><Button variant="outline"><Download className="mr-2 h-4 w-4" />匯出 CSV</Button></div>
      {loading ? <div className="text-center py-12"><Loader2 className="mx-auto h-6 w-6 animate-spin" /></div> :
        <Card><CardContent className="p-0"><Table><TableHeader><TableRow><TableHead>時間</TableHead><TableHead>操作</TableHead><TableHead>操作者</TableHead><TableHead>資源</TableHead></TableRow></TableHeader>
          <TableBody>{logs.length === 0 ? <TableRow><TableCell colSpan={4} className="text-center text-muted-foreground">暫無審計記錄</TableCell></TableRow> :
            logs.map((log: any) => (
              <TableRow key={log.id}><TableCell className="text-sm whitespace-nowrap">{formatDate(log.created_at)}</TableCell>
                <TableCell><Badge variant="outline" className="text-xs font-mono">{log.action}</Badge></TableCell>
                <TableCell className="text-sm">{log.actor_user_id}</TableCell>
                <TableCell className="text-sm text-muted-foreground">{log.resource_id || '-'}</TableCell></TableRow>
            ))}</TableBody></Table></CardContent></Card>}
    </div>
  );
}
