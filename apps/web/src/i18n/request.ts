import { cookies } from 'next/headers';
import { getRequestConfig } from 'next-intl/server';

export default getRequestConfig(async () => {
  const value = (await cookies()).get('locale')?.value;
  const locale = value === 'pl' ? 'pl' : 'en';
  return { locale, messages: (await import(`../../messages/${locale}.json`)).default };
});
