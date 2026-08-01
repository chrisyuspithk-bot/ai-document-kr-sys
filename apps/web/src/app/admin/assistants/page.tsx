'use client';

import { Card, CardContent } from '@/components/ui/card';
import { Bot } from 'lucide-react';

export default function AdminAssistantsPage() {
  return (
    <div className="space-y-6">
      <div><h1 className="text-2xl font-bold tracking-tight">AI 助理配置</h1><p className="text-muted-foreground text-sm">管理 AI 助理的提示詞、模型和知識庫範圍</p></div>
      <Card><CardContent className="flex flex-col items-center justify-center gap-3 py-16 text-center">
        <div className="rounded-full bg-primary/10 p-4"><Bot className="h-8 w-8 text-primary" /></div>
        <div><p className="text-sm font-medium">尚無 AI 助理設定</p><p className="text-sm text-muted-foreground mt-1">AI 助理設定功能即將推出。目前所有對話使用預設助理。</p></div>
      </CardContent></Card>
    </div>
  );
}
