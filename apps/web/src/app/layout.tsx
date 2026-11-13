import { Inter, Inter_Tight, JetBrains_Mono } from 'next/font/google';
import { NextIntlClientProvider } from 'next-intl';
import { getLocale } from 'next-intl/server';
import { AppShell } from './app-shell';
import { Providers } from './providers';
import './globals.css';

const body = Inter({ subsets: ['latin', 'latin-ext'], variable: '--font-body-source' });
const display = Inter_Tight({ subsets: ['latin', 'latin-ext'], variable: '--font-display-source' });
const mono = JetBrains_Mono({ subsets: ['latin', 'latin-ext'], variable: '--font-mono-source' });

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = await getLocale();
  return (
    <html lang={locale}>
      <body className={`${body.variable} ${display.variable} ${mono.variable}`}>
        <NextIntlClientProvider>
          <Providers>
            <AppShell>{children}</AppShell>
          </Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
