'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Download, Loader2 } from 'lucide-react';
import { useApiToken, apiFetch, apiFetchJson } from '@/lib/client-api';
import { formatDate } from '@/lib/utils';

export default function AdminAuditPage() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const token = useApiToken();

  useEffect(() => {
    if (!token) return;
    apiFetchJson<{ items: any[] }>('/api/v1/audit-logs?limit=100', token)
      .then((data) => setLogs(data.items ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  async function handleExport() {
    if (!token || exporting) return;
    setExporting(true);
    try {
      const res = await apiFetch('/api/v1/audit-logs/export', token);
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'audit_logs.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } finally { setExporting(false); }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between"><div><h1 className="text-2xl font-bold tracking-tight">審計日誌</h1><p className="text-muted-foreground text-sm">檢視所有系統操作記錄</p></div><Button variant="outline" onClick={handleExport} disabled={exporting}>{exporting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}匯出 CSV</Button></div>
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
