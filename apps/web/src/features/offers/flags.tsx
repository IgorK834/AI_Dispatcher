import { useTranslations } from 'next-intl';
import { Pill, type PillLevel } from '@/components/ui/pill';

const ATTENTION = new Set([
  'SUSPICIOUS_TEXT',
  'INVALID_PROVIDER_RECORD',
  'MISSING_CAPACITY_DATA',
  'MISSING_COORDINATES',
  'MISSING_REVENUE',
  'ZERO_WEIGHT',
]);

/** A quality flag in plain words; a code without a translation shows the generic text, never the raw code. */
export function FlagPill({ code }: { code: string }) {
  const t = useTranslations('offers.flag');
  const level: PillLevel = ATTENTION.has(code) ? 'attention' : 'quiet';
  return (
    <span title={code}>
      <Pill level={level}>{t.has(code) ? t(code) : t('UNKNOWN')}</Pill>
    </span>
  );
}

const PROVENANCE_LEVEL: Record<string, PillLevel> = {
  source: 'quiet',
  user: 'quiet',
  derived: 'info',
  inferred: 'info',
  default: 'attention',
  generated_mock: 'synthetic',
};

export function ProvenancePill({ value }: { value: string }) {
  const t = useTranslations('offers.provenance');
  return <Pill level={PROVENANCE_LEVEL[value] ?? 'quiet'}>{t.has(value) ? t(value) : value}</Pill>;
}
