'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { CalendarCheck, Upload, FileAudio, Loader2, ListChecks, Plus } from 'lucide-react';
import { useApiToken, apiFetch, apiFetchJson } from '@/lib/client-api';
import { formatDate, formatBytes } from '@/lib/utils';

const STATUS_MAP: Record<string, { label: string; variant: 'default' | 'secondary' | 'success' | 'warning' | 'destructive' }> = {
  pending: { label: '待處理', variant: 'warning' },
  transcribing: { label: '轉寫中', variant: 'secondary' },
  completed: { label: '已完成', variant: 'success' },
  failed: { label: '失敗', variant: 'destructive' },
};

export default function MeetingsPage() {
  const [meetings, setMeetings] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [folder, setFolder] = useState('');
  const [meetingDate, setMeetingDate] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState('');
  const token = useApiToken();

  const fetchMeetings = useCallback(async () => {
    try {
      const data = await apiFetchJson<any[]>('/api/v1/meetings', token);
      setMeetings(data);
    } catch {}
    setLoading(false);
  }, [token]);

  useEffect(() => { if (token) fetchMeetings(); }, [token, fetchMeetings]);

  async function fetchDetail(id: string) {
    try {
      const data = await apiFetchJson<any>('/api/v1/meetings/' + id, token);
      setSelected(data);
    } catch {}
  }

  async function handleCreate() {
    if (!title.trim()) return;
    try {
      const meeting = await apiFetchJson<any>('/api/v1/meetings', token, {
        method: 'POST',
        body: JSON.stringify({ title, description, folder: folder || undefined, meeting_date: meetingDate || undefined }),
      });
      if (files.length > 0) {
        const formData = new FormData();
        files.forEach((f) => formData.append('files', f));
        const res = await apiFetch(`/api/v1/meetings/${meeting.id}/recordings`, token, { method: 'POST', body: formData });
        if (!res.ok) throw new Error('Upload failed');
      }
      setShowCreate(false); setTitle(''); setDescription(''); setFolder(''); setMeetingDate(''); setFiles([]);
      fetchMeetings();
    } catch { setError('建立會議失敗。'); }
  }

  async function handleSummarize(meetingId: string) {
    try {
      await apiFetchJson(`/api/v1/meetings/${meetingId}/summarize`, token, { method: 'POST' });
      fetchDetail(meetingId);
    } catch {}
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold tracking-tight">會議中心</h1><p className="text-muted-foreground text-sm">管理會議錄音、轉寫和摘要</p></div>
        <Dialog open={showCreate} onOpenChange={setShowCreate}>
          <DialogTrigger asChild><Button onClick={() => setShowCreate(true)}><Plus className="mr-2 h-4 w-4" />建立會議</Button></DialogTrigger>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader><DialogTitle>建立新會議</DialogTitle><DialogDescription>新增會議並上傳錄音檔案</DialogDescription></DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2"><Label htmlFor="title">會議標題 *</Label><Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="會議標題" /></div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2"><Label htmlFor="date">會議日期</Label><Input id="date" type="date" value={meetingDate} onChange={(e) => setMeetingDate(e.target.value)} /></div>
                <div className="space-y-2"><Label htmlFor="folder">資料夾</Label><Input id="folder" value={folder} onChange={(e) => setFolder(e.target.value)} placeholder="e.g. 2026 董事會" /></div>
              </div>
              <div className="space-y-2"><Label htmlFor="desc">描述</Label><Textarea id="desc" value={description} onChange={(e) => setDescription(e.target.value)} rows={2} /></div>
              <div className="space-y-2">
                <Label>上傳錄音</Label>
                <div className="border-2 border-dashed rounded-lg p-6 text-center">
                  <Upload className="mx-auto h-8 w-8 text-muted-foreground mb-2" />
                  <p className="text-sm text-muted-foreground mb-1">拖放檔案至此，或點擊選擇</p>
                  <p className="text-xs text-muted-foreground">支援：MP3、WAV、M4A、FLAC、WEBM</p>
                  <Input type="file" className="mt-3" accept="audio/*" multiple onChange={(e) => { if (e.target.files) setFiles(Array.from(e.target.files)); }} />
                  {files.length > 0 && <div className="mt-2 text-xs space-y-1">{files.map((f, i) => <div key={i} className="flex items-center gap-2 justify-center text-muted-foreground"><FileAudio className="h-3 w-3" />{f.name} ({formatBytes(f.size)})</div>)}</div>}
                </div>
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
            </div>
            <DialogFooter><Button variant="outline" onClick={() => setShowCreate(false)}>取消</Button><Button onClick={handleCreate} disabled={!title.trim()}>建立會議</Button></DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1 space-y-4">
          <Card><CardHeader><CardTitle className="text-lg">會議列表</CardTitle></CardHeader>
            <CardContent className="p-0">
              {loading ? <div className="p-4 text-center"><Loader2 className="mx-auto h-5 w-5 animate-spin" /></div>
                : meetings.length === 0 ? <p className="p-4 text-sm text-muted-foreground">尚未有會議記錄</p>
                  : <div className="divide-y">{meetings.map((m: any) => (
                    <button key={m.id} className="w-full text-left p-4 hover:bg-muted/50 transition-colors" onClick={() => fetchDetail(m.id)}>
                      <div className="flex items-center justify-between"><p className="font-medium text-sm truncate">{m.title}</p>
                        {m.status && <Badge variant={STATUS_MAP[m.status]?.variant || 'secondary'} className="text-xs">{STATUS_MAP[m.status]?.label || m.status}</Badge>}
                      </div>
                      {m.meeting_date && <p className="text-xs text-muted-foreground mt-1"><CalendarCheck className="inline h-3 w-3 mr-1" />{formatDate(m.meeting_date)}</p>}
                    </button>
                  ))}</div>}
            </CardContent></Card>
        </div>
        <div className="lg:col-span-2">
          {selected ? (
            <Tabs defaultValue="recordings">
              <TabsList><TabsTrigger value="recordings">錄音</TabsTrigger><TabsTrigger value="transcript">逐字稿</TabsTrigger><TabsTrigger value="summary">摘要</TabsTrigger></TabsList>
              <TabsContent value="recordings">
                <Card><CardHeader><CardTitle className="text-lg">{selected.meeting.title}</CardTitle><CardDescription>{selected.meeting.description}</CardDescription></CardHeader>
                  <CardContent>{selected.recordings.map((r: any) => (
                    <div key={r.id} className="flex items-center justify-between py-3 border-b last:border-0">
                      <div className="flex items-center gap-3"><FileAudio className="h-5 w-5 text-muted-foreground" /><div><p className="font-medium text-sm">{r.filename}</p><p className="text-xs text-muted-foreground">{formatBytes(r.file_size)}{r.duration_seconds && ` · ${Math.floor(r.duration_seconds / 60)} 分鐘`}</p></div></div>
                      <div className="flex items-center gap-2">
                        <Badge variant={STATUS_MAP[r.status]?.variant || 'secondary'} className="text-xs">{STATUS_MAP[r.status]?.label || r.status}</Badge>
                        {r.status === 'completed' && <Button size="sm" variant="outline" onClick={() => handleSummarize(selected.meeting.id)}>摘要</Button>}
                      </div>
                    </div>
                  ))}</CardContent></Card>
              </TabsContent>
              <TabsContent value="transcript">
                <Card><CardHeader><CardTitle className="text-lg">逐字稿</CardTitle></CardHeader>
                  <CardContent>{selected.transcript ? <pre className="whitespace-pre-wrap text-sm font-sans">{selected.transcript.full_text}</pre> : <p className="text-sm text-muted-foreground">尚未轉寫</p>}</CardContent></Card>
              </TabsContent>
              <TabsContent value="summary">
                <Card><CardHeader><CardTitle className="text-lg">會議摘要</CardTitle></CardHeader>
                  <CardContent>{selected.summary ? (
                    <div className="space-y-4">
                      <div><h4 className="font-medium text-sm mb-1">摘要</h4><p className="text-sm">{selected.summary.summary}</p></div>
                      {selected.summary.decisions?.length > 0 && <div><h4 className="font-medium text-sm mb-1 flex items-center gap-1"><ListChecks className="h-4 w-4" />決定事項</h4><ul className="list-disc list-inside text-sm space-y-1">{selected.summary.decisions.map((d: string, i: number) => <li key={i}>{d}</li>)}</ul></div>}
                      {selected.summary.action_items?.length > 0 && <div><h4 className="font-medium text-sm mb-1">行動項目</h4><div className="space-y-1">{selected.summary.action_items.map((a: any, i: number) => <div key={i} className="flex items-center gap-2 text-sm"><Badge variant="outline" className="text-xs">{a.owner || '未指定'}</Badge><span>{a.task}</span></div>)}</div></div>}
                      {selected.summary.key_points?.length > 0 && <div><h4 className="font-medium text-sm mb-1">重點</h4><div className="flex flex-wrap gap-1">{selected.summary.key_points.map((k: string, i: number) => <Badge key={i} variant="secondary" className="text-xs">{k}</Badge>)}</div></div>}
                    </div>
                  ) : <div className="text-center py-8"><p className="text-sm text-muted-foreground">尚未生成摘要</p>{selected.transcript && <Button className="mt-3" onClick={() => handleSummarize(selected.meeting.id)}>生成摘要</Button>}</div>}</CardContent></Card>
              </TabsContent>
            </Tabs>
          ) : <Card className="h-full flex items-center justify-center min-h-[400px]"><div className="text-center space-y-3"><CalendarCheck className="mx-auto h-12 w-12 text-muted-foreground" /><p className="text-muted-foreground">選擇一個會議以檢視詳情</p></div></Card>}
        </div>
      </div>
    </div>
  );
}
