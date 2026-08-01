'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { FileText, Loader2, Download, Check, X, Send } from 'lucide-react';
import { useApiToken, apiFetch, apiFetchJson } from '@/lib/client-api';
import { formatDate } from '@/lib/utils';
import ReactMarkdown from 'react-markdown';

const ACTION_PATH: Record<string, string> = {
  submit: 'submit',
  approve: 'approve',
  reject: 'reject',
  revise: 'revise',
};

export default function DocGenPage() {
  const [prompt, setPrompt] = useState('');
  const [templateId, setTemplateId] = useState('');
  const [loading, setLoading] = useState(false);
  const [generated, setGenerated] = useState<any>(null);
  const [revisionPrompt, setRevisionPrompt] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [templates, setTemplates] = useState<any[]>([]);
  const token = useApiToken();

  useEffect(() => {
    if (!token) return;
    apiFetchJson<any[]>('/api/v1/templates', token)
      .then(setTemplates)
      .catch(() => {});
  }, [token]);

  async function fetchHistory() {
    if (historyLoading || history.length > 0) return;
    setHistoryLoading(true);
    try {
      const data = await apiFetchJson<any[]>('/api/v1/gen-documents', token);
      setHistory(data);
    } catch { setHistory([]); }
    finally { setHistoryLoading(false); }
  }

  async function handleGenerate() {
    if (!prompt.trim()) return;
    setLoading(true); setError('');
    try {
      const data = await apiFetchJson('/api/v1/generate', token, {
        method: 'POST',
        body: JSON.stringify({ prompt, template_id: templateId || undefined, title: prompt.slice(0, 80) }),
      });
      setGenerated(data);
    } catch { setError('文件生成失敗，請重試。'); }
    finally { setLoading(false); }
  }

  async function handleAction(docId: string, action: string) {
    const actionPath = ACTION_PATH[action];
    if (!actionPath) return;
    setSubmitting(true); setError('');
    try {
      const body: any = {};
      if (action === 'revise') {
        body.prompt = revisionPrompt;
      }
      const data = await apiFetchJson(`/api/v1/gen-documents/${docId}/${actionPath}`, token, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (action === 'revise') {
        setGenerated(data);
        setRevisionPrompt('');
      } else {
        setGenerated(data);
      }
    } catch { setError('操作失敗。'); }
    finally { setSubmitting(false); }
  }

  async function handleExport(docId: string, fmt: 'docx' | 'pdf') {
    setSubmitting(true);
    try {
      await apiFetchJson(`/api/v1/gen-documents/${docId}/export?fmt=${fmt}`, token, { method: 'POST' });
      const res = await apiFetch(`/api/v1/gen-documents/${docId}/download/${fmt}`, token);
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${generated?.title || 'document'}.${fmt}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch { setError('匯出失敗，請先核准文件。'); }
    finally { setSubmitting(false); }
  }

  return (
    <div className="space-y-6">
      <div><h1 className="text-2xl font-bold tracking-tight">文件生成</h1><p className="text-muted-foreground text-sm">使用 AI 生成提案、報告、會議記錄等文件</p></div>
      <Tabs defaultValue="generate" onValueChange={(v) => { if (v === 'history') fetchHistory(); }}>
        <TabsList><TabsTrigger value="generate">生成文件</TabsTrigger><TabsTrigger value="history">生成記錄</TabsTrigger></TabsList>
        <TabsContent value="generate" className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-lg">建立新文件</CardTitle><CardDescription>描述您需要的文件內容，選擇範本後生成</CardDescription></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>提示詞</Label>
                <Textarea placeholder="描述您需要生成的文件內容…例如：撰寫一份關於長者社區支援服務的年度計劃書" value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={5} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>選擇範本（可選）</Label>
                  <Select value={templateId} onValueChange={setTemplateId}>
                    <SelectTrigger><SelectValue placeholder="無範本" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">無範本</SelectItem>
                      {templates.map((t: any) => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>參考知識庫（可選）</Label>
                  <Select><SelectTrigger><SelectValue placeholder="不指定" /></SelectTrigger><SelectContent><SelectItem value="">不指定</SelectItem></SelectContent></Select>
                </div>
              </div>
              <Button onClick={handleGenerate} disabled={loading || !prompt.trim()} className="w-full">
                {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}<FileText className="mr-2 h-4 w-4" />生成文件
              </Button>
              {error && <p className="text-sm text-destructive">{error}</p>}
            </CardContent>
          </Card>
          {generated && (
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div><CardTitle className="text-lg">{generated.title}</CardTitle>
                  <CardDescription>狀態：<Badge>{generated.status === 'draft' ? '草稿' : generated.status === 'submitted' ? '已提交' : generated.status === 'approved' ? '已核准' : generated.status === 'rejected' ? '已退回' : generated.status}</Badge></CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled={submitting} onClick={() => handleExport(generated.id, 'docx')}><Download className="mr-1 h-4 w-4" />匯出 Word</Button>
                  <Button variant="outline" size="sm" disabled={submitting} onClick={() => handleExport(generated.id, 'pdf')}><Download className="mr-1 h-4 w-4" />匯出 PDF</Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="markdown-body border rounded-lg p-6 bg-background min-h-40"><ReactMarkdown>{generated.content || '（無內容）'}</ReactMarkdown></div>
                <div className="mt-4 space-y-3">
                  <div className="space-y-2"><Label>修改指示</Label><div className="flex gap-2"><Input placeholder="描述需要的修改…" value={revisionPrompt} onChange={(e) => setRevisionPrompt(e.target.value)} /><Button variant="outline" disabled={!revisionPrompt.trim() || submitting} onClick={() => handleAction(generated.id, 'revise')}>修改</Button></div></div>
                  <div className="flex gap-2 justify-end border-t pt-3">
                    <Button variant="outline" onClick={() => handleAction(generated.id, 'submit')} disabled={submitting}><Send className="mr-1 h-4 w-4" />提交審批</Button>
                    <Button variant="default" className="bg-green-600 hover:bg-green-700" onClick={() => handleAction(generated.id, 'approve')} disabled={submitting}><Check className="mr-1 h-4 w-4" />核准</Button>
                    <Button variant="destructive" onClick={() => handleAction(generated.id, 'reject')} disabled={submitting}><X className="mr-1 h-4 w-4" />退回</Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
        <TabsContent value="history">
          <Card><CardHeader><CardTitle className="text-lg">生成記錄</CardTitle></CardHeader><CardContent className="p-0">
            {historyLoading ? <div className="text-center py-12"><Loader2 className="mx-auto h-6 w-6 animate-spin" /></div> :
              history.length === 0 ? <p className="text-sm text-muted-foreground p-6">尚未有生成記錄</p> :
              <Table><TableHeader><TableRow><TableHead>標題</TableHead><TableHead>狀態</TableHead><TableHead>版本</TableHead><TableHead>建立日期</TableHead></TableRow></TableHeader>
                <TableBody>{history.map((doc: any) => (
                  <TableRow key={doc.id}><TableCell className="font-medium">{doc.title}</TableCell>
                    <TableCell><Badge variant="outline" className="text-xs">{doc.status === 'draft' ? '草稿' : doc.status === 'submitted' ? '已提交' : doc.status === 'approved' ? '已核准' : doc.status === 'rejected' ? '已退回' : doc.status}</Badge></TableCell>
                    <TableCell className="text-sm text-muted-foreground">v{doc.version}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{formatDate(doc.created_at)}</TableCell></TableRow>
                ))}</TableBody></Table>}
          </CardContent></Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
