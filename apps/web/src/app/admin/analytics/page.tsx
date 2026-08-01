import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { BarChart3, Users, FileText, MessageSquare } from 'lucide-react';

const stats = [
  { label: 'Token 用量（本月）', value: '125,430', icon: BarChart3, description: '較上月 +12%' },
  { label: '活躍用戶', value: '48', icon: Users, description: '本週活躍用戶' },
  { label: '文件總數', value: '1,247', icon: FileText, description: '已索引文件' },
  { label: '生成次數', value: '89', icon: MessageSquare, description: '本月 AI 生成次數' },
];

export default function AdminAnalyticsPage() {
  return (
    <div className="space-y-6">
      <div><h1 className="text-2xl font-bold tracking-tight">系統分析</h1><p className="text-muted-foreground text-sm">系統使用狀況和指標</p></div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <Card key={s.label}>
            <CardHeader className="flex flex-row items-center justify-between pb-2"><CardTitle className="text-sm font-medium">{s.label}</CardTitle><s.icon className="h-4 w-4 text-muted-foreground" /></CardHeader>
            <CardContent><div className="text-2xl font-bold">{s.value}</div><p className="text-xs text-muted-foreground">{s.description}</p></CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
