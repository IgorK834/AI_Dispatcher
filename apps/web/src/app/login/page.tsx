import { useTranslations } from 'next-intl';
import { Suspense } from 'react';
import { LanguageSwitch } from '@/components/language-switch';
import { Pill } from '@/components/ui/pill';
import { VanSide } from '@/components/vehicle/van-side';
import { LoginForm } from '@/features/auth';

const FACTS = ['vans', 'variants', 'withoutAi'] as const;

/** The hint with the local account names appears only outside production (APP_ENV=local). */
function isLocalEnvironment(): boolean {
  const configured = process.env.NEXT_PUBLIC_APP_ENV;
  return configured ? configured === 'local' : process.env.NODE_ENV !== 'production';
}

export default function LoginPage() {
  const t = useTranslations('auth');
  const common = useTranslations('common');
  return (
    <div className="flex min-h-screen flex-col">
      <header className="mx-auto flex w-full max-w-[1440px] items-center justify-between gap-4 px-10 py-5">
        <span className="font-display text-xl font-bold text-ink">{common('appTitle')}</span>
        <LanguageSwitch />
      </header>
      <main className="mx-auto flex w-full max-w-[1440px] flex-1 flex-wrap items-stretch gap-4 px-10 py-6">
        <section
          aria-label={common('appTitle')}
          className="flex min-w-0 flex-[999_1_520px] flex-col justify-between gap-10 rounded-card bg-surface p-12 shadow-card"
        >
          <div className="flex max-w-xl flex-col gap-4">
            <Pill level="synthetic" className="self-start">
              {t('syntheticDemo')}
            </Pill>
            <h1 className="text-5xl">{t('headline')}</h1>
            <p className="text-base text-ink2">{t('lead')}</p>
          </div>
          <VanSide label="BUS-01" width={460} decorative />
          <ul className="grid grid-cols-3 gap-3">
            {FACTS.map((fact) => (
              <li key={fact} className="flex flex-col gap-1 rounded-inner bg-well p-4">
                <span className="text-xs text-ink3">{t(`facts.${fact}.label`)}</span>
                <span className="font-display text-xl text-ink">{t(`facts.${fact}.value`)}</span>
                <span className="text-xs text-ink3">{t(`facts.${fact}.note`)}</span>
              </li>
            ))}
          </ul>
        </section>
        <section
          aria-labelledby="signin-title"
          className="flex max-w-[480px] flex-[1_1_400px] flex-col justify-center gap-5 rounded-card bg-surface p-10 shadow-card"
        >
          <div className="flex flex-col gap-1">
            <h2 id="signin-title" className="font-display text-3xl font-medium text-ink">
              {t('title')}
            </h2>
            <p className="text-ink2">{t('subtitle')}</p>
          </div>
          <Suspense>
            <LoginForm showLocalHint={isLocalEnvironment()} />
          </Suspense>
        </section>
      </main>
      <footer className="mx-auto flex w-full max-w-[1440px] flex-wrap justify-between gap-3 px-10 pb-6 pt-4 text-xs text-ink3">
        <span>{t('footer.synthetic')}</span>
        <span>{t('footer.mvp')}</span>
      </footer>
    </div>
  );
}
