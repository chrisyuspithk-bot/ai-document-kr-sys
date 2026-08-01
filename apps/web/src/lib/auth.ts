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

      // Refresh access token if expired
      const accessToken = token.accessToken as string | undefined;
      if (accessToken) {
        try {
          const parts = accessToken.split('.');
          if (parts.length !== 3) return token;
          const payload = JSON.parse(Buffer.from(parts[1]!, 'base64').toString());
          const now = Math.floor(Date.now() / 1000);
          if (payload.exp && now >= payload.exp - 60) {
            const refreshToken = token.refreshToken as string | undefined;
            if (refreshToken) {
              const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: refreshToken }),
              });
              if (res.ok) {
                const data = await res.json();
                token.accessToken = data.access_token;
                token.refreshToken = data.refresh_token;
              }
            }
          }
        } catch { /* keep existing token if refresh fails */ }
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
