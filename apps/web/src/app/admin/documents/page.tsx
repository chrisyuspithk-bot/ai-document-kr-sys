import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Upload } from 'lucide-react';

export default function AdminDocumentsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between"><div><h1 className="text-2xl font-bold tracking-tight">文件管理</h1><p className="text-muted-foreground text-sm">上傳和管理所有知識庫文件</p></div><Button><Upload className="mr-2 h-4 w-4" />上傳文件</Button></div>
      <Card><CardHeader><CardTitle className="text-lg">所有文件</CardTitle></CardHeader><CardContent><div className="border-2 border-dashed rounded-lg p-12 text-center"><Upload className="mx-auto h-10 w-10 text-muted-foreground mb-3" /><p className="text-muted-foreground">拖放文件至此，或點擊上傳</p><p className="text-xs text-muted-foreground mt-1">支援格式：PDF、Word、Excel、PPT、TXT、HTML、圖片</p></div></CardContent></Card>
    </div>
  );
}
