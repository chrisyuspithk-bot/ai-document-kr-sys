import NextAuth from 'next-auth';
import Credentials from 'next-auth/providers/credentials';
import type { User } from '@/types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Credentials({
      name: 'credentials',
      credentials: {
        username: { label: 'Username', type: 'text' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
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
          const data = await res.json();
          return {
            id: data.user.id,
            email: data.user.email,
            name: data.user.display_name,
            accessToken: data.access_token,
            refreshToken: data.refresh_token,
            roles: data.user.roles,
            permissions: data.user.permissions,
            orgId: data.user.org_id,
          };
        } catch {
          return null;
        }
      },
    }),
  ],
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
});
