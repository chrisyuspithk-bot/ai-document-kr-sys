'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { useSession } from 'next-auth/react';
import { useTheme } from 'next-themes';
import { Loader2, Save } from 'lucide-react';

export default function SettingsPage() {
  const { data: session } = useSession();
  const { theme, setTheme } = useTheme();
  const [displayName, setDisplayName] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (session?.user?.name) setDisplayName(session.user.name);
  }, [session]);

  if (!session) {
    return <div className="text-center py-12"><Loader2 className="mx-auto h-6 w-6 animate-spin" /></div>;
  }

  function handleSave() {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="space-y-6">
      <div><h1 className="text-2xl font-bold tracking-tight">設定</h1><p className="text-muted-foreground text-sm">管理您的個人資料和偏好</p></div>

      <Card>
        <CardHeader><CardTitle className="text-lg">帳戶資料</CardTitle><CardDescription>您的登入資訊</CardDescription></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2"><Label>用戶名稱</Label><Input value={session.user?.name || ''} readOnly /></div>
            <div className="space-y-2"><Label>電郵</Label><Input value={session.user?.email || ''} readOnly /></div>
          </div>
          <div className="space-y-2"><Label>顯示名稱</Label><Input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="您的顯示名稱" /></div>
          <Button onClick={handleSave}>{saved ? <><Loader2 className="mr-2 h-4 w-4 animate-spin" />已儲存</> : <><Save className="mr-2 h-4 w-4" />儲存變更</>}</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-lg">外觀</CardTitle><CardDescription>選擇您偏好的主題模式</CardDescription></CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Button variant={theme === 'light' ? 'default' : 'outline'} onClick={() => setTheme('light')}>淺色模式</Button>
            <Button variant={theme === 'dark' ? 'default' : 'outline'} onClick={() => setTheme('dark')}>深色模式</Button>
            <Button variant={theme === 'system' ? 'default' : 'outline'} onClick={() => setTheme('system')}>跟隨系統</Button>
          </div>
          <div className="flex items-center gap-2 pt-2">
            <Badge variant="secondary">目前主題</Badge>
            <span className="text-sm text-muted-foreground">{theme === 'light' ? '淺色' : theme === 'dark' ? '深色' : '跟隨系統'}</span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
