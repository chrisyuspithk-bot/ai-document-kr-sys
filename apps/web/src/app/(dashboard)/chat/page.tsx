'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Sparkles, User, Bot, Loader2, Send, ExternalLink, Plus, Trash2, MessageSquare } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useApiToken, apiFetchJson } from '@/lib/client-api';
import { formatDate } from '@/lib/utils';
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
  const [convId, setConvId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<any[]>([]);
  const [convLoading, setConvLoading] = useState(false);
  const token = useApiToken();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => { scrollRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const fetchConversations = useCallback(async () => {
    if (!token) return;
    setConvLoading(true);
    try {
      const data = await apiFetchJson<any[]>('/api/v1/conversations', token);
      setConversations(data);
    } catch {}
    finally { setConvLoading(false); }
  }, [token]);

  useEffect(() => { fetchConversations(); }, [fetchConversations]);

  async function loadConversation(id: string) {
    try {
      const data = await apiFetchJson<any>(`/api/v1/conversations/${id}`, token);
      setConvId(id);
      setMessages((data.messages || []).map((m: any) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        citations: m.citations || null,
      })));
    } catch {}
  }

  async function deleteConversation(id: string) {
    try {
      await apiFetchJson(`/api/v1/conversations/${id}`, token, { method: 'DELETE' });
      if (convId === id) { setConvId(null); setMessages([]); }
      fetchConversations();
    } catch {}
  }

  function newConversation() {
    setConvId(null);
    setMessages([]);
  }

  async function handleSend() {
    if (!input.trim() || loading) return;
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);
    try {
      const data = await apiFetchJson<ChatResponse>('/api/v1/chat', token, {
        method: 'POST',
        body: JSON.stringify({ query: userMsg.content, conversation_id: convId || undefined }),
      });
      if (!convId) { setConvId(data.conversation_id); fetchConversations(); }
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
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Conversation sidebar */}
      <div className="w-64 shrink-0 flex flex-col gap-2">
        <Button variant="outline" className="justify-start" onClick={newConversation}>
          <Plus className="mr-2 h-4 w-4" />新對話
        </Button>
        <Card className="flex-1 overflow-hidden">
          <ScrollArea className="h-full">
            {convLoading ? <div className="p-4 text-center"><Loader2 className="mx-auto h-4 w-4 animate-spin" /></div> :
              conversations.length === 0 ? <p className="p-4 text-sm text-muted-foreground text-center">尚無對話記錄</p> :
              <div className="p-1">
                {conversations.map((c: any) => (
                  <div key={c.id} className={cn(
                    'group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm cursor-pointer transition-colors hover:bg-accent',
                    convId === c.id && 'bg-accent'
                  )}>
                    <button className="flex-1 text-left truncate" onClick={() => loadConversation(c.id)}>
                      <MessageSquare className="inline h-3 w-3 mr-1.5 text-muted-foreground" />
                      {c.title || '未命名對話'}
                    </button>
                    <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100 shrink-0" onClick={(e) => { e.stopPropagation(); deleteConversation(c.id); }}>
                      <Trash2 className="h-3 w-3 text-destructive" />
                    </Button>
                  </div>
                ))}
              </div>
            }
          </ScrollArea>
        </Card>
      </div>

      {/* Chat area */}
      <div className="flex-1 flex flex-col gap-4 min-w-0">
        <div><h1 className="text-2xl font-bold tracking-tight">AI 對話</h1><p className="text-muted-foreground text-sm">向 AI 助理提問，獲取知識庫資訊</p></div>
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
    </div>
  );
}
