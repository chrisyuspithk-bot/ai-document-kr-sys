'use client';

import { useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { BookOpen, Loader2 } from 'lucide-react';

export default function LoginPage() {
  const csrfRef = useRef<HTMLInputElement>(null);
  const [csrfReady, setCsrfReady] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch('/api/auth/csrf')
      .then(r => r.json())
      .then(d => {
        if (csrfRef.current) csrfRef.current.value = d.csrfToken;
        setCsrfReady(true);
      });
  }, []);

  return (
    <Card className="w-full max-w-md mx-4">
      <CardHeader className="text-center">
        <div className="flex justify-center mb-4">
          <div className="rounded-full bg-primary/10 p-3">
            <BookOpen className="h-8 w-8 text-primary" />
          </div>
        </div>
        <CardTitle className="text-2xl">登入仁愛堂 AI 平台</CardTitle>
        <CardDescription>
          請使用您的帳戶登入
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form action="/api/auth/callback/credentials" method="POST"
          onSubmit={() => setLoading(true)} className="space-y-4">
          <input type="hidden" name="csrfToken" ref={csrfRef} />
          <div className="space-y-2">
            <Label htmlFor="username">用戶名稱</Label>
            <Input
              id="username"
              name="username"
              type="text"
              placeholder="username"
              required
              autoFocus
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">密碼</Label>
            <Input
              id="password"
              name="password"
              type="password"
              placeholder="••••••••"
              required
            />
          </div>
          <Button type="submit" className="w-full" disabled={loading || !csrfReady}>
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            登入
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
