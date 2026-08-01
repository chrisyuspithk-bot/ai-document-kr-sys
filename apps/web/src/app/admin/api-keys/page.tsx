'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Plus, Copy, Loader2, Ban } from 'lucide-react';
import { formatDate } from '@/lib/utils';
import { toast } from 'sonner';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function AdminApiKeysPage() {
  const [keys, setKeys] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [keyName, setKeyName] = useState('');
  const [created, setCreated] = useState<any>(null);
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') || '' : '';

  async function fetchKeys() {
    try {
      const res = await fetch(`${API_BASE}/api/v1/api-keys?include_inactive=true`, { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setKeys(await res.json());
    } catch {}
    setLoading(false);
  }
  useEffect(() => { if (token) fetchKeys(); }, [token]);

  async function handleCreate() {
    if (!keyName.trim()) return;
    try {
      const res = await fetch(`${API_BASE}/api/v1/api-keys`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify({ name: keyName }) });
      if (!res.ok) throw new Error('Create failed');
      setCreated(await res.json()); fetchKeys();
    } catch { toast.error('建立失敗'); }
  }

  async function handleRevoke(id: string) {
    await fetch(`${API_BASE}/api/v1/api-keys/${id}/revoke`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
    toast.success('已撤銷'); fetchKeys();
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between"><div><h1 className="text-2xl font-bold tracking-tight">API 密鑰管理</h1><p className="text-muted-foreground text-sm">管理外部系統整合用的 API 密鑰</p></div>
        <Dialog open={showCreate} onOpenChange={(o) => { setShowCreate(o); if (!o) setCreated(null); }}>
          <DialogTrigger asChild><Button onClick={() => { setShowCreate(true); setKeyName(''); setCreated(null); }}><Plus className="mr-2 h-4 w-4" />建立密鑰</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>{created ? '密鑰已建立' : '建立 API 密鑰'}</DialogTitle></DialogHeader>
            {created ? (
              <div className="space-y-4 py-4">
                <div className="rounded-lg bg-yellow-50 dark:bg-yellow-950 border border-yellow-200 dark:border-yellow-800 p-4"><p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">請安全儲存此密鑰。此密鑰不會再次顯示。</p></div>
                <div className="space-y-2"><Label>密鑰</Label><div className="flex gap-2"><Input value={created.raw_key} readOnly className="font-mono text-sm" /><Button variant="outline" size="icon" onClick={() => { navigator.clipboard.writeText(created.raw_key); toast.success('已複製'); }}><Copy className="h-4 w-4" /></Button></div></div>
              </div>
            ) : (
              <div className="space-y-4 py-4"><div className="space-y-2"><Label>密鑰名稱 *</Label><Input value={keyName} onChange={(e) => setKeyName(e.target.value)} placeholder="e.g. 內部系統連接器" /></div></div>
            )}
            <DialogFooter>{created ? <Button onClick={() => setShowCreate(false)}>關閉</Button> : <><Button variant="outline" onClick={() => setShowCreate(false)}>取消</Button><Button onClick={handleCreate} disabled={!keyName.trim()}>建立</Button></>}</DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      {loading ? <div className="text-center py-12"><Loader2 className="mx-auto h-6 w-6 animate-spin" /></div> :
        <Card><CardContent className="p-0"><Table><TableHeader><TableRow><TableHead>名稱</TableHead><TableHead>前綴</TableHead><TableHead>狀態</TableHead><TableHead>最後使用</TableHead><TableHead>建立日期</TableHead><TableHead className="w-24">操作</TableHead></TableRow></TableHeader>
          <TableBody>{keys.length === 0 ? <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">暫無 API 密鑰</TableCell></TableRow> :
            keys.map((k: any) => (
              <TableRow key={k.id}><TableCell className="font-medium">{k.name}</TableCell><TableCell className="font-mono text-sm text-muted-foreground">{k.key_prefix}</TableCell>
                <TableCell><Badge variant={k.is_active ? 'success' : 'secondary'}>{k.is_active ? '啟用' : '已撤銷'}</Badge></TableCell>
                <TableCell className="text-muted-foreground text-sm">{k.last_used_at ? formatDate(k.last_used_at) : '從未使用'}</TableCell>
                <TableCell className="text-muted-foreground text-sm">{formatDate(k.created_at)}</TableCell>
                <TableCell>{k.is_active && <Button variant="ghost" size="icon" onClick={() => handleRevoke(k.id)}><Ban className="h-4 w-4 text-destructive" /></Button>}</TableCell></TableRow>
            ))}</TableBody></Table></CardContent></Card>}
    </div>
  );
}
