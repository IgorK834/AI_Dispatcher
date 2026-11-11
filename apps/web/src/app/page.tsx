import { useTranslations } from 'next-intl';
import { LanguageSwitch } from '../components/language-switch';

export default function Home() {
  const t = useTranslations('common');
  return (
    <main className="home-card">
      <LanguageSwitch />
      <h1>{t('appTitle')}</h1>
      <p>{t('description')}</p>
    </main>
  );
}
