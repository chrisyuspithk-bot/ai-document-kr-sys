'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Bot, Cpu, BookOpen } from 'lucide-react';
import { MODELS } from '@/lib/constants';

export default function AdminAssistantsPage() {
  return (
    <div className="space-y-6">
      <div><h1 className="text-2xl font-bold tracking-tight">AI 助理配置</h1><p className="text-muted-foreground text-sm">管理 AI 助理的提示詞、模型和知識庫範圍</p></div>

      <Card>
        <CardHeader><CardTitle className="text-lg">預設助理</CardTitle><CardDescription>系統預設的 AI 助理，所有用戶均可使用</CardDescription></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-start gap-4 p-4 rounded-lg border">
            <div className="rounded-full bg-primary/10 p-2"><Bot className="h-5 w-5 text-primary" /></div>
            <div className="flex-1">
              <div className="flex items-center gap-2"><h3 className="font-medium">通用助理</h3><Badge variant="secondary" className="text-xs">預設</Badge></div>
              <p className="text-sm text-muted-foreground mt-1">根據知識庫內容回答問題，支援繁體中文和英文</p>
              <div className="flex items-center gap-4 mt-3">
                <span className="flex items-center gap-1 text-xs text-muted-foreground"><Cpu className="h-3 w-3" />DeepSeek-V4-Flash</span>
                <span className="flex items-center gap-1 text-xs text-muted-foreground"><BookOpen className="h-3 w-3" />所有知識庫</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

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
