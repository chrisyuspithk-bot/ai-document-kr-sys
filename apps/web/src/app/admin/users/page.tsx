'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Plus, Loader2 } from 'lucide-react';
import { useApiToken, apiFetchJson } from '@/lib/client-api';
import { formatDate } from '@/lib/utils';

export default function AdminUsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const token = useApiToken();

  useEffect(() => {
    if (!token) return;
    apiFetchJson<any[]>('/api/v1/users', token)
      .then(setUsers)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [token]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between"><div><h1 className="text-2xl font-bold tracking-tight">用戶管理</h1><p className="text-muted-foreground text-sm">管理用戶帳戶、角色和權限</p></div><Button><Plus className="mr-2 h-4 w-4" />建立用戶</Button></div>
      {loading ? <div className="text-center py-12"><Loader2 className="mx-auto h-6 w-6 animate-spin" /></div> :
        <Card><CardContent className="p-0"><Table><TableHeader><TableRow><TableHead>用戶名稱</TableHead><TableHead>顯示名稱</TableHead><TableHead>電郵</TableHead><TableHead>角色</TableHead><TableHead>狀態</TableHead><TableHead>建立日期</TableHead></TableRow></TableHeader>
          <TableBody>{users.length === 0 ? <TableRow><TableCell colSpan={6} className="text-center text-muted-foreground">暫無用戶</TableCell></TableRow> :
            users.map((u: any) => (
              <TableRow key={u.id}><TableCell className="font-medium">{u.username}</TableCell><TableCell>{u.full_name || u.username}</TableCell><TableCell className="text-muted-foreground text-sm">{u.email}</TableCell>
                <TableCell>{u.is_superuser ? <Badge variant="secondary" className="text-xs">系統管理員</Badge> : <Badge variant="outline" className="text-xs">用戶</Badge>}</TableCell>
                <TableCell><Badge variant={u.is_active ? 'success' : 'secondary'}>{u.is_active ? '啟用' : '停用'}</Badge></TableCell>
                <TableCell className="text-muted-foreground text-sm">{formatDate(u.created_at)}</TableCell></TableRow>
            ))}</TableBody></Table></CardContent></Card>}
    </div>
  );
}
