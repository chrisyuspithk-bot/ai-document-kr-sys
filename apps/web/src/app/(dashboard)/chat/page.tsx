'use client';

import { useState, useRef, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Sparkles, User, Bot, Loader2, Send, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useApiToken, apiFetchJson } from '@/lib/client-api';
import ReactMarkdown from 'react-markdown';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Array<{ document_id: string; document_title: string; chunk_text: string; score: number }> | null;
}

interface ChatResponse {
  answer: string;
  conversation_id: string;
  citations?: Array<{ document_id: string; document_title: string; snippet?: string; score: number }>;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [assistantId, setAssistantId] = useState<string>('');
  const token = useApiToken();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => { scrollRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  async function handleSend() {
    if (!input.trim() || loading) return;
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    try {
      const data = await apiFetchJson<ChatResponse>('/api/v1/chat', token, {
        method: 'POST',
        body: JSON.stringify({ query: userMsg.content }),
      });
      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.answer || '',
        citations: data.citations?.map((c) => ({
          document_id: c.document_id,
          document_title: c.document_title,
          chunk_text: c.snippet || '',
          score: c.score,
        })) || null,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      setMessages((prev) => [...prev, { id: (Date.now() + 1).toString(), role: 'assistant', content: '生成回覆時發生錯誤。請稍後重試。' }]);
    } finally { setLoading(false); }
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col gap-4">
      <div className="flex items-center justify-between">
        <div><h1 className="text-2xl font-bold tracking-tight">AI 對話</h1><p className="text-muted-foreground text-sm">向 AI 助理提問，獲取知識庫資訊</p></div>
        <Select value={assistantId} onValueChange={setAssistantId}>
          <SelectTrigger className="w-48"><SelectValue placeholder="選擇 AI 助理" /></SelectTrigger>
          <SelectContent><SelectItem value="">預設助理</SelectItem></SelectContent>
        </Select>
      </div>
      <Card className="flex-1 flex flex-col overflow-hidden">
        <ScrollArea className="flex-1 p-4">
          {messages.length === 0 ? (
            <div className="flex h-full items-center justify-center text-center">
              <div className="space-y-4">
                <div className="mx-auto rounded-full bg-primary/10 p-4 w-fit"><Sparkles className="h-8 w-8 text-primary" /></div>
                <div><p className="text-lg font-medium">開始新對話</p><p className="text-sm text-muted-foreground mt-1">輸入您的問題，AI 助理會根據知識庫內容回答</p></div>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((msg) => (
                <div key={msg.id} className={cn('flex gap-3', msg.role === 'user' ? 'justify-end' : '')}>
                  {msg.role === 'assistant' && <div className="rounded-full bg-primary/10 p-2 h-fit"><Bot className="h-4 w-4 text-primary" /></div>}
                  <div className={cn('max-w-[80%] rounded-lg px-4 py-3', msg.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted')}>
                    {msg.role === 'assistant' ? <div className="markdown-body text-sm"><ReactMarkdown>{msg.content}</ReactMarkdown></div> : <p className="text-sm whitespace-pre-wrap">{msg.content}</p>}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-3 border-t pt-2"><p className="text-xs font-medium mb-1">引用來源：</p>
                        <div className="flex flex-wrap gap-1">{msg.citations.map((c, i) => <Badge key={i} variant="outline" className="text-xs gap-1"><ExternalLink className="h-2 w-2" />{c.document_title}</Badge>)}</div>
                      </div>
                    )}
                  </div>
                  {msg.role === 'user' && <div className="rounded-full bg-primary p-2 h-fit"><User className="h-4 w-4 text-primary-foreground" /></div>}
                </div>
              ))}
              {loading && <div className="flex gap-3"><div className="rounded-full bg-primary/10 p-2 h-fit"><Bot className="h-4 w-4 text-primary" /></div><div className="bg-muted rounded-lg px-4 py-3"><Loader2 className="h-4 w-4 animate-spin" /></div></div>}
              <div ref={scrollRef} />
            </div>
          )}
        </ScrollArea>
        <div className="border-t p-4">
          <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="flex gap-2">
            <Input placeholder="輸入您的問題…" value={input} onChange={(e) => setInput(e.target.value)} disabled={loading} className="flex-1" />
            <Button type="submit" disabled={loading || !input.trim()}>{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}</Button>
          </form>
        </div>
      </Card>
    </div>
  );
}
