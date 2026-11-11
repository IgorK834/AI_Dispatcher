'use client';

import { useLocale, useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';

export function LanguageSwitch() {
  const t = useTranslations('common');
  const current = useLocale();
  const router = useRouter();
  return (
    <div className="language-switch" role="group" aria-label={t('language.label')}>
      {(['en', 'pl'] as const).map((locale) => (
        <button
          key={locale}
          type="button"
          aria-pressed={current === locale}
          onClick={() => {
            document.cookie = `locale=${locale}; Path=/; SameSite=Lax`;
            router.refresh();
          }}
        >
          {t(`language.${locale}`)}
        </button>
      ))}
    </div>
  );
}
