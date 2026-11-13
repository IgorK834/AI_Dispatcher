'use client';

import { useLocale, useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';
import { Segmented } from '@/components/ui/segmented';

export function LanguageSwitch() {
  const t = useTranslations('common');
  const current = useLocale() === 'pl' ? 'pl' : 'en';
  const router = useRouter();
  return (
    <Segmented
      label={t('language.label')}
      value={current}
      options={[
        { value: 'en', label: t('language.en') },
        { value: 'pl', label: t('language.pl') },
      ]}
      onValueChange={(locale) => {
        document.cookie = `locale=${locale}; Path=/; SameSite=Lax`;
        router.refresh();
      }}
    />
  );
}
