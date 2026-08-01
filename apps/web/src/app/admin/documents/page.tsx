'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Upload, Loader2, FileText, Trash2 } from 'lucide-react';
import { useApiToken, apiFetchJson } from '@/lib/client-api';
import { formatDate } from '@/lib/utils';

const DOC_STATUS: Record<string, { label: string; variant: 'default' | 'secondary' | 'success' | 'destructive' }> = {
  draft: { label: '草稿', variant: 'secondary' },
  processing: { label: '處理中', variant: 'secondary' },
  indexed: { label: '已索引', variant: 'success' },
  failed: { label: '失敗', variant: 'destructive' },
};

export default function AdminDocumentsPage() {
  const [kbs, setKbs] = useState<any[]>([]);
  const [selectedKbId, setSelectedKbId] = useState<string>('');
  const [documents, setDocuments] = useState<any[]>([]);
  const [kbLoading, setKbLoading] = useState(true);
  const [docLoading, setDocLoading] = useState(false);
  const token = useApiToken();

  useEffect(() => {
    if (!token) return;
    apiFetchJson<any[]>('/api/v1/knowledge-bases', token)
      .then((data) => { setKbs(data); if (data.length > 0 && !selectedKbId) setSelectedKbId(data[0].id); })
      .catch(() => {})
      .finally(() => setKbLoading(false));
  }, [token]);

  const fetchDocuments = useCallback(async () => {
    if (!selectedKbId || !token) return;
    setDocLoading(true);
    try {
      const data = await apiFetchJson<any[]>(`/api/v1/knowledge-bases/${selectedKbId}/documents`, token);
      setDocuments(data);
    } catch { setDocuments([]); }
    finally { setDocLoading(false); }
  }, [selectedKbId, token]);

  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  async function handleDelete(docId: string) {
    try {
      await apiFetchJson(`/api/v1/documents/${docId}`, token, { method: 'DELETE' });
      fetchDocuments();
    } catch {}
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold tracking-tight">文件管理</h1><p className="text-muted-foreground text-sm">管理所有知識庫中的文件</p></div>
        <div className="flex items-center gap-3">
          <Select value={selectedKbId} onValueChange={setSelectedKbId}>
            <SelectTrigger className="w-56"><SelectValue placeholder="選擇知識庫" /></SelectTrigger>
            <SelectContent>
              {kbs.map((kb: any) => <SelectItem key={kb.id} value={kb.id}>{kb.name} ({kb.document_count || 0})</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-lg">{kbs.find((k: any) => k.id === selectedKbId)?.name || '所有文件'}</CardTitle></CardHeader>
        <CardContent className="p-0">
          {kbLoading || docLoading ? <div className="text-center py-12"><Loader2 className="mx-auto h-6 w-6 animate-spin" /></div> :
            <Table>
              <TableHeader><TableRow><TableHead>文件名稱</TableHead><TableHead>類型</TableHead><TableHead>狀態</TableHead><TableHead>版本</TableHead><TableHead>建立日期</TableHead><TableHead className="w-24">操作</TableHead></TableRow></TableHeader>
              <TableBody>
                {documents.length === 0 ? (
                  <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground py-8">
                    <div className="flex flex-col items-center gap-2"><Upload className="h-8 w-8 text-muted-foreground/50" /><p>暫無文件，請先在知識庫中上傳文件</p></div>
                  </TableCell></TableRow>
                ) : documents.map((doc: any) => (
                  <TableRow key={doc.id}>
                    <TableCell className="font-medium"><FileText className="inline h-4 w-4 mr-2 text-muted-foreground" />{doc.title || doc.filename}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{doc.file_type || '-'}</TableCell>
                    <TableCell><Badge variant={DOC_STATUS[doc.status]?.variant || 'secondary'} className="text-xs">{DOC_STATUS[doc.status]?.label || doc.status}</Badge></TableCell>
                    <TableCell className="text-sm text-muted-foreground">v{doc.version || 1}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{formatDate(doc.created_at)}</TableCell>
                    <TableCell><Button variant="ghost" size="icon" onClick={() => handleDelete(doc.id)}><Trash2 className="h-4 w-4 text-destructive" /></Button></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          }
        </CardContent>
      </Card>
    </div>
  );
}
