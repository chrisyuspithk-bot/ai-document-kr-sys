import { getRequestConfig } from 'next-intl/server';
import { cookies } from 'next/headers';

export const locales = ['zh', 'en'] as const;
export type Locale = (typeof locales)[number];

export default getRequestConfig(async () => {
  const cookieStore = await cookies();
  let locale = cookieStore.get('NEXT_LOCALE')?.value || 'zh';
  if (!locales.includes(locale as Locale)) locale = 'zh';
  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
