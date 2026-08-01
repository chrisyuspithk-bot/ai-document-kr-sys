import createMiddleware from 'next-intl/middleware';
import { NextRequest, NextResponse } from 'next/server';
import { getToken } from 'next-auth/jwt';
import { locales } from '@/i18n/request';

const intlMiddleware = createMiddleware({
  locales,
  defaultLocale: 'zh',
  localeDetection: true,
});

const publicPaths = ['/login'];
const staticPaths = ["/_next", "/static", "/favicon.ico"];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Handle i18n first
  const intlResponse = intlMiddleware(request);
  if (intlResponse) return intlResponse;

  if (staticPaths.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  if (pathname.startsWith("/api/auth") || pathname.startsWith("/_next")) {
    return NextResponse.next();
  }

  const token = await getToken({
    req: request,
    secret: process.env.AUTH_SECRET,
  });

  // Check public paths against the pathname without locale prefix
  const pathWithoutLocale = pathname.replace(/^\/(zh|en)/, '') || '/';
  const isPublic = publicPaths.some((p) => pathWithoutLocale.startsWith(p));

  if (!token && !isPublic) {
    const url = new URL("/login", request.url);
    url.searchParams.set("callbackUrl", pathname);
    return NextResponse.redirect(url);
  }

  if (token && isPublic) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
