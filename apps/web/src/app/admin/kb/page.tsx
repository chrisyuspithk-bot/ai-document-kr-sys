'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Plus, Loader2, Trash2 } from 'lucide-react';
import { useApiToken, apiFetchJson } from '@/lib/client-api';
import { formatDate } from '@/lib/utils';

export default function AdminKBPage() {
  const [kbs, setKbs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const token = useApiToken();

  async function fetchKBs() {
    try {
      const data = await apiFetchJson<any[]>('/api/v1/knowledge-bases', token);
      setKbs(data);
    } catch {}
    setLoading(false);
  }
  useEffect(() => { if (token) fetchKBs(); }, [token]);

  async function handleCreate() {
    if (!name.trim()) return;
    try {
      await apiFetchJson('/api/v1/knowledge-bases', token, {
        method: 'POST',
        body: JSON.stringify({ name, description }),
      });
      setShowCreate(false); setName(''); setDescription(''); fetchKBs();
    } catch {}
  }

  async function handleDelete(id: string) {
    try {
      await apiFetchJson(`/api/v1/knowledge-bases/${id}`, token, { method: 'DELETE' });
    } catch {}
    fetchKBs();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold tracking-tight">知識庫管理</h1><p className="text-muted-foreground text-sm">管理知識庫、上傳文件、設定權限</p></div>
        <Dialog open={showCreate} onOpenChange={setShowCreate}>
          <DialogTrigger asChild><Button onClick={() => setShowCreate(true)}><Plus className="mr-2 h-4 w-4" />建立知識庫</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>建立新知識庫</DialogTitle></DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2"><Label>知識庫名稱 *</Label><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. 社會服務政策文件" /></div>
              <div className="space-y-2"><Label>描述</Label><Textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} /></div>
            </div>
            <DialogFooter><Button variant="outline" onClick={() => setShowCreate(false)}>取消</Button><Button onClick={handleCreate} disabled={!name.trim()}>建立</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      {loading ? <div className="text-center py-12"><Loader2 className="mx-auto h-6 w-6 animate-spin" /></div> :
        <Card><CardContent className="p-0"><Table><TableHeader><TableRow><TableHead>名稱</TableHead><TableHead>文件數量</TableHead><TableHead>狀態</TableHead><TableHead>建立日期</TableHead><TableHead className="w-24">操作</TableHead></TableRow></TableHeader>
          <TableBody>{kbs.length === 0 ? <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground">暫無知識庫</TableCell></TableRow> :
            kbs.map((kb: any) => (
              <TableRow key={kb.id}><TableCell className="font-medium">{kb.name}</TableCell><TableCell>{kb.document_count || 0}</TableCell>
                <TableCell><Badge variant={kb.is_active ? 'success' : 'secondary'}>{kb.is_active ? '啟用' : '停用'}</Badge></TableCell>
                <TableCell className="text-muted-foreground text-sm">{formatDate(kb.created_at)}</TableCell>
                <TableCell><Button variant="ghost" size="icon" onClick={() => handleDelete(kb.id)}><Trash2 className="h-4 w-4 text-destructive" /></Button></TableCell>
              </TableRow>
            ))}</TableBody></Table></CardContent></Card>}
    </div>
  );
}
