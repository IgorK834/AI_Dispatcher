'use client';

import { useTranslations } from 'next-intl';
import { Banner } from '@/components/ui/banner';
import { Button } from '@/components/ui/button';
import { API_BASE_URL } from '@/lib/api/client';

/** The full-page state for an API that is down or blocked by CORS (FEAT-005 section 8). */
export function ApiUnreachable({ onRetry }: { onRetry: () => void }) {
  const t = useTranslations('common.apiUnreachable');
  return (
    <section className="mx-auto flex max-w-xl flex-col gap-4 p-10">
      <h1 className="font-display text-2xl font-medium text-ink">
        {t('title', { url: API_BASE_URL })}
      </h1>
      <Banner level="error">{t('hint')}</Banner>
      <div>
        <Button variant="primary" onClick={onRetry}>
          {t('retry')}
        </Button>
      </div>
    </section>
  );
}
