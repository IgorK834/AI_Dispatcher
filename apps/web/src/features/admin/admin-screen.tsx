'use client';

import { useTranslations } from 'next-intl';
import { AiStatus } from './ai-status';
import { CostProfileView } from './cost-profile';
import { GenerateForm } from './generate-form';
import { ResetSection } from './reset-section';

/** Demo data, cost profile and AI status; only administrators reach it (the route guard decides). */
export function AdminScreen() {
  const t = useTranslations('admin');
  return (
    <div className="flex min-w-0 flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1>{t('title')}</h1>
        <p className="text-ink2">{t('subtitle')}</p>
      </header>
      <div className="grid min-w-0 gap-6 lg:grid-cols-2">
        <GenerateForm />
        <ResetSection />
        <AiStatus />
        <CostProfileView />
      </div>
    </div>
  );
}
