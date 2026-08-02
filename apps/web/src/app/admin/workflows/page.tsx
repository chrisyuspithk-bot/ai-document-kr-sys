'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Workflow, Play, CheckCircle2, XCircle, Clock, Loader2, Plus, Eye } from 'lucide-react';
import { useApiToken, apiFetchJson } from '@/lib/client-api';
import { toast } from 'sonner';

interface WorkflowDef { id: string; name: string; description: string | null; status: string; trigger_type: string; steps: any[]; version: number; created_at: string; }
interface WorkflowRun { id: string; workflow_id: string; status: string; trigger_type: string; current_step: number; created_at: string; completed_at: string | null; }
interface ApprovalStep { id: string; run_id: string; step_order: number; approver_id: string | null; status: string; comment: string | null; decided_at: string | null; created_at: string; }

export default function AdminWorkflowsPage() {
  const [workflows, setWorkflows] = useState<WorkflowDef[]>([]);
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [approvals, setApprovals] = useState<ApprovalStep[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [selectedRun, setSelectedRun] = useState<WorkflowRun | null>(null);
  const [runApprovals, setRunApprovals] = useState<ApprovalStep[]>([]);
  const token = useApiToken();

  const [form, setForm] = useState({ name: '', description: '', trigger_type: 'manual' });

  const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const h = (tok: string) => ({ 'Content-Type': 'application/json', Authorization: `Bearer ${tok}` });

  async function load() {
    if (!token) return;
    setLoading(true);
    try {
      const [wfs, wfRuns, apps] = await Promise.all([
        apiFetchJson<WorkflowDef[]>('/api/v1/workflows', token),
        apiFetchJson<WorkflowRun[]>('/api/v1/workflows/runs', token).catch(() => []),
        apiFetchJson<ApprovalStep[]>('/api/v1/workflows/approvals/all', token).catch(() => []),
      ]);
      setWorkflows(wfs);
      setRuns(wfRuns);
      setApprovals(apps);
    } catch { toast.error('載入失敗'); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [token]);

  async function create() {
    if (!form.name.trim() || !token) return;
    try {
      await fetch(`${API}/api/v1/workflows`, { method: 'POST', headers: h(token), body: JSON.stringify({...form, steps: []}) });
      toast.success('流程已建立');
      setCreateOpen(false);
      setForm({ name: '', description: '', trigger_type: 'manual' });
      load();
    } catch { toast.error('建立失敗'); }
  }

  async function activate(id: string) {
    if (!token) return;
    try {
      await fetch(`${API}/api/v1/workflows/${id}`, { method: 'PATCH', headers: h(token), body: JSON.stringify({ status: 'active' }) });
      load();
    } catch { toast.error('啟用失敗'); }
  }

  async function triggerWorkflow(id: string) {
    if (!token) return;
    try {
      await fetch(`${API}/api/v1/workflows/${id}/trigger`, { method: 'POST', headers: h(token) });
      toast.success('流程已觸發');
      load();
    } catch { toast.error('觸發失敗'); }
  }

  async function decideApproval(stepId: string, decision: 'approve' | 'reject') {
    if (!token) return;
    try {
      await fetch(`${API}/api/v1/workflows/approvals/${stepId}/${decision}`, { method: 'POST', headers: h(token), body: JSON.stringify({ comment: decision === 'approve' ? '已批准' : '已拒絕' }) });
      load();
    } catch { toast.error('操作失敗'); }
  }

  async function viewRun(run: WorkflowRun) {
    if (!token) return;
    try {
      const detail = await apiFetchJson<any>(`/api/v1/workflows/runs/${run.id}`, token);
      setSelectedRun(detail);
      setRunApprovals(detail.approvals || []);
    } catch { toast.error('載入失敗'); }
  }

  const statusBadge = (s: string) => {
    const map: Record<string, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string }> = {
      active: { variant: 'default', label: '啟用' },
      draft: { variant: 'secondary', label: '草稿' },
      archived: { variant: 'outline', label: '封存' },
      pending: { variant: 'secondary', label: '等待中' },
      waiting_approval: { variant: 'secondary', label: '等待審批' },
      running: { variant: 'default', label: '執行中' },
      completed: { variant: 'default', label: '已完成' },
      rejected: { variant: 'destructive', label: '已拒絕' },
      failed: { variant: 'destructive', label: '失敗' },
    };
    const m = map[s] || { variant: 'outline' as const, label: s };
    return <Badge variant={m.variant}>{m.label}</Badge>;
  };

  if (loading) return <div className="text-center py-12"><Loader2 className="mx-auto h-6 w-6 animate-spin" /></div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold tracking-tight">工作流程</h1><p className="text-muted-foreground text-sm">設計和管理審批流程、查看執行歷史</p></div>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild><Button size="sm"><Plus className="h-4 w-4 mr-1" />新增流程</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>新增工作流程</DialogTitle></DialogHeader>
            <div className="space-y-3">
              <div><Label>名稱</Label><Input value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="流程名稱" /></div>
              <div><Label>描述</Label><Textarea value={form.description} onChange={e => setForm({...form, description: e.target.value})} placeholder="流程描述" /></div>
              <Button onClick={create} className="w-full">建立</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <Tabs defaultValue="definitions">
        <TabsList>
          <TabsTrigger value="definitions">流程定義</TabsTrigger>
          <TabsTrigger value="runs">執行歷史</TabsTrigger>
          <TabsTrigger value="approvals">審批隊列 {approvals.length > 0 && `(${approvals.length})`}</TabsTrigger>
        </TabsList>

        <TabsContent value="definitions" className="space-y-4 mt-4">
          {workflows.length === 0 ? (
            <Card><CardContent className="py-8 text-center text-muted-foreground">尚未建立任何工作流程</CardContent></Card>
          ) : workflows.map(w => (
            <Card key={w.id}>
              <CardContent className="p-4">
                <div className="flex items-start gap-4">
                  <div className="rounded-full bg-primary/10 p-2"><Workflow className="h-5 w-5 text-primary" /></div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-medium">{w.name}</h3>
                      {statusBadge(w.status)}
                      <Badge variant="outline" className="text-xs">v{w.version}</Badge>
                    </div>
                    {w.description && <p className="text-sm text-muted-foreground mt-1">{w.description}</p>}
                    <p className="text-xs text-muted-foreground mt-1">觸發方式: {w.trigger_type} · {w.steps?.length || 0} 個步驟</p>
                    <div className="flex gap-2 mt-3">
                      {w.status === 'draft' && <Button size="sm" onClick={() => activate(w.id)}>啟用</Button>}
                      {w.status === 'active' && <Button size="sm" variant="outline" onClick={() => triggerWorkflow(w.id)}><Play className="h-3 w-3 mr-1" />觸發</Button>}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="runs" className="space-y-4 mt-4">
          {runs.length === 0 ? (
            <Card><CardContent className="py-8 text-center text-muted-foreground">尚無執行記錄</CardContent></Card>
          ) : runs.map(r => (
            <div key={r.id} className="flex items-center justify-between rounded-lg border p-3">
              <div className="flex items-center gap-3">
                {r.status === 'completed' ? <CheckCircle2 className="h-5 w-5 text-green-500" /> :
                 r.status === 'rejected' ? <XCircle className="h-5 w-5 text-destructive" /> :
                 <Clock className="h-5 w-5 text-muted-foreground" />}
                <div>
                  <p className="text-sm font-medium">{workflows.find(w => w.id === r.workflow_id)?.name || r.workflow_id}</p>
                  <p className="text-xs text-muted-foreground">{r.trigger_type} · {new Date(r.created_at).toLocaleString()}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {statusBadge(r.status)}
                <Button size="sm" variant="ghost" onClick={() => viewRun(r)}><Eye className="h-4 w-4" /></Button>
              </div>
            </div>
          ))}
        </TabsContent>

        <TabsContent value="approvals" className="space-y-4 mt-4">
          {approvals.length === 0 ? (
            <Card><CardContent className="py-8 text-center text-muted-foreground">尚無待審批項目</CardContent></Card>
          ) : approvals.map(a => (
            <div key={a.id} className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <p className="text-sm font-medium">步驟 {a.step_order + 1}</p>
                <p className="text-xs text-muted-foreground">{new Date(a.created_at).toLocaleString()}</p>
              </div>
              <div className="flex gap-2">
                <Button size="sm" variant="default" onClick={() => decideApproval(a.id, 'approve')}><CheckCircle2 className="h-3 w-3 mr-1" />批准</Button>
                <Button size="sm" variant="destructive" onClick={() => decideApproval(a.id, 'reject')}><XCircle className="h-3 w-3 mr-1" />拒絕</Button>
              </div>
            </div>
          ))}
        </TabsContent>
      </Tabs>

      <Dialog open={!!selectedRun} onOpenChange={() => setSelectedRun(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>執行詳情</DialogTitle></DialogHeader>
          {selectedRun && (
            <div className="space-y-3">
              <div className="flex items-center gap-2">{statusBadge(selectedRun.status)}<span className="text-sm text-muted-foreground">{new Date(selectedRun.created_at).toLocaleString()}</span></div>
              <ScrollArea className="max-h-60">
                <div className="space-y-2">
                  {runApprovals.map(a => (
                    <div key={a.id} className="rounded-lg border p-2">
                      <div className="flex items-center justify-between">
                        <span className="text-sm">步驟 {a.step_order + 1}</span>
                        {a.status === 'approved' ? <Badge variant="default">已批准</Badge> :
                         a.status === 'rejected' ? <Badge variant="destructive">已拒絕</Badge> :
                         <Badge variant="secondary">等待中</Badge>}
                      </div>
                      {a.comment && <p className="text-xs text-muted-foreground mt-1">{a.comment}</p>}
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
