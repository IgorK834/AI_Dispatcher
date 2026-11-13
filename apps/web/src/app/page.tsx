import { useTranslations } from 'next-intl';

export default function Home() {
  const t = useTranslations('common');
  return (
    <section className="flex max-w-3xl flex-col gap-2 rounded-card bg-surface p-6 shadow-card">
      <h1>{t('appTitle')}</h1>
      <p className="text-ink2">{t('description')}</p>
    </section>
  );
}
