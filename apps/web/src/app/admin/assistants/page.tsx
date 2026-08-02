'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Bot, Cpu, BookOpen, Plus, Loader2, RefreshCw, History } from 'lucide-react';
import { MODELS } from '@/lib/constants';
import { useApiToken, apiFetchJson } from '@/lib/client-api';
import { toast } from 'sonner';

interface Assistant {
  id: string; name: string; description: string | null;
  model: string; mode: string; is_active: boolean; version: number;
  system_prompt: string; kb_ids: string[] | null; tools: string[] | null;
  created_at: string;
}

interface AssistantVersion {
  id: string; version: number; system_prompt: string; model: string;
  mode: string; created_at: string;
}

export default function AdminAssistantsPage() {
  const [assistants, setAssistants] = useState<Assistant[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [versionsOpen, setVersionsOpen] = useState<string | null>(null);
  const [versions, setVersions] = useState<AssistantVersion[]>([]);
  const token = useApiToken();

  const [form, setForm] = useState({ name: '', description: '', system_prompt: '', model: 'deepseek-v4-flash', mode: 'internal' });

  async function load() {
    if (!token) return;
    setLoading(true);
    try {
      const data = await apiFetchJson<Assistant[]>('/api/v1/assistants?include_inactive=true', token);
      setAssistants(data);
    } catch { toast.error('載入助理列表失敗'); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [token]);

  async function createAssistant() {
    if (!form.name.trim()) return;
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/assistants`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(form),
      });
      toast.success('助理已建立');
      setCreateOpen(false);
      setForm({ name: '', description: '', system_prompt: '', model: 'deepseek-v4-flash', mode: 'internal' });
      load();
    } catch { toast.error('建立失敗'); }
  }

  async function toggleActive(id: string, active: boolean) {
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/assistants/${id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ is_active: !active }),
      });
      load();
    } catch { toast.error('更新失敗'); }
  }

  async function loadVersions(id: string) {
    try {
      const data = await apiFetchJson<AssistantVersion[]>(`/api/v1/assistants/${id}/versions`, token!);
      setVersions(data);
      setVersionsOpen(id);
    } catch { toast.error('載入版本失敗'); }
  }

  async function rollback(id: string, version: number) {
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/assistants/${id}/rollback/${version}`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` },
      });
      toast.success(`已回滾到版本 ${version}`);
      load();
      loadVersions(id);
    } catch { toast.error('回滾失敗'); }
  }

  if (loading) return <div className="text-center py-12"><Loader2 className="mx-auto h-6 w-6 animate-spin" /></div>;

  const modeLabel = (m: string) => m === 'internal' ? '內部' : '聯網';
  const modeVariant = (m: string) => (m === 'internal' ? 'secondary' : 'default') as 'secondary' | 'default';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold tracking-tight">AI 助理配置</h1><p className="text-muted-foreground text-sm">管理 AI 助理的提示詞、模型和知識庫範圍</p></div>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild><Button size="sm"><Plus className="h-4 w-4 mr-1" />新增助理</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>新增 AI 助理</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div><Label>名稱</Label><Input value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="助理名稱" /></div>
              <div><Label>描述</Label><Input value={form.description} onChange={e => setForm({...form, description: e.target.value})} placeholder="簡短描述" /></div>
              <div><Label>系統提示詞</Label><Textarea value={form.system_prompt} onChange={e => setForm({...form, system_prompt: e.target.value})} placeholder="你是一個專業的..." rows={3} /></div>
              <div><Label>模型</Label><Select value={form.model} onValueChange={v => setForm({...form, model: v})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{MODELS.map(m => <SelectItem key={m.id} value={m.id}>{m.name}</SelectItem>)}</SelectContent>
              </Select></div>
              <div><Label>模式</Label><Select value={form.mode} onValueChange={v => setForm({...form, mode: v})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="internal">僅內部知識庫</SelectItem><SelectItem value="web">聯網搜尋</SelectItem></SelectContent>
              </Select></div>
              <Button onClick={createAssistant} className="w-full">建立</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {assistants.length === 0 ? (
        <Card><CardContent className="py-8 text-center text-muted-foreground">尚未建立任何 AI 助理</CardContent></Card>
      ) : (
        <div className="space-y-4">
          {assistants.map(a => (
            <Card key={a.id}>
              <CardContent className="p-4">
                <div className="flex items-start gap-4">
                  <div className="rounded-full bg-primary/10 p-2"><Bot className="h-5 w-5 text-primary" /></div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-medium">{a.name}</h3>
                      <Badge variant={modeVariant(a.mode)} className="text-xs">{modeLabel(a.mode)}</Badge>
                      {!a.is_active && <Badge variant="outline" className="text-xs">已停用</Badge>}
                      <Badge variant="secondary" className="text-xs">v{a.version}</Badge>
                    </div>
                    {a.description && <p className="text-sm text-muted-foreground mt-1">{a.description}</p>}
                    <div className="flex items-center gap-4 mt-3">
                      <span className="flex items-center gap-1 text-xs text-muted-foreground"><Cpu className="h-3 w-3" />{MODELS.find(m => m.id === a.model)?.name || a.model}</span>
                      <span className="flex items-center gap-1 text-xs text-muted-foreground"><BookOpen className="h-3 w-3" />{a.kb_ids?.length ? `${a.kb_ids.length} 個知識庫` : '所有知識庫'}</span>
                    </div>
                    <div className="flex gap-2 mt-3">
                      <Button size="sm" variant="outline" onClick={() => loadVersions(a.id)}><History className="h-3 w-3 mr-1" />版本</Button>
                      <Button size="sm" variant={a.is_active ? 'outline' : 'default'} onClick={() => toggleActive(a.id, a.is_active)}>
                        {a.is_active ? '停用' : '啟用'}
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={!!versionsOpen} onOpenChange={() => setVersionsOpen(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>版本歷史</DialogTitle></DialogHeader>
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {versions.map(v => (
              <div key={v.id} className="flex items-center justify-between rounded-lg border p-3">
                <div>
                  <p className="text-sm font-medium">版本 {v.version}</p>
                  <p className="text-xs text-muted-foreground truncate max-w-[300px]">{v.system_prompt}</p>
                  <p className="text-xs text-muted-foreground">{v.model} · {new Date(v.created_at).toLocaleDateString()}</p>
                </div>
                <Button size="sm" variant="outline" onClick={() => rollback(versionsOpen!, v.version)}><RefreshCw className="h-3 w-3 mr-1" />回滾</Button>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      <Card>
        <CardHeader><CardTitle className="text-lg">可用模型</CardTitle><CardDescription>系統中已配置的 AI 模型</CardDescription></CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-3">
            {MODELS.map((m) => (
              <div key={m.id} className="flex items-center gap-3 rounded-lg border p-3">
                <Cpu className="h-4 w-4 text-primary shrink-0" />
                <div>
                  <p className="text-sm font-medium">{m.name}</p>
                  <p className="text-xs text-muted-foreground font-mono">{m.id}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
