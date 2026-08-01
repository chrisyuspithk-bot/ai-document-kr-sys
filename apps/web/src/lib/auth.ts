import NextAuth from 'next-auth';
import type { User } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const credentialsProvider = {
  id: 'credentials',
  name: 'credentials',
  type: 'credentials' as const,
  credentials: {
    username: { label: 'Username', type: 'text' },
    password: { label: 'Password', type: 'password' },
  },
  authorize: async (credentials: Record<string, string>) => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: credentials.username,
          password: credentials.password,
        }),
      });
      if (!res.ok) return null;
      const { access_token, refresh_token } = await res.json();

      const meRes = await fetch(`${API_BASE}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${access_token}` },
      });
      if (!meRes.ok) return null;
      const user = await meRes.json();

      return {
        id: user.id,
        email: user.email,
        name: user.full_name || user.username,
        accessToken: access_token,
        refreshToken: refresh_token,
        roles: user.roles || [],
        permissions: user.permissions || [],
        orgId: user.org_id,
      };
    } catch {
      return null;
    }
  },
};

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [credentialsProvider as any],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = (user as User & { accessToken: string }).accessToken;
        token.refreshToken = (user as User & { refreshToken: string }).refreshToken;
        token.roles = (user as User & { roles: string[] }).roles;
        token.permissions = (user as User & { permissions: string[] }).permissions;
        token.orgId = (user as User & { orgId: string }).orgId;
      }
      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string;
      session.user.roles = token.roles as string[];
      session.user.permissions = token.permissions as string[];
      session.user.orgId = token.orgId as string;
      return session;
    },
  },
  pages: { signIn: '/login' },
  session: { strategy: 'jwt' },
  trustHost: true,
  secret: process.env.AUTH_SECRET,
});
