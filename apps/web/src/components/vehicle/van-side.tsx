'use client';

import { useTranslations } from 'next-intl';

type VanSideProps = {
  /** The vehicle label drawn on the plate, for example "BUS-01". */
  label: string;
  width?: number;
  accent?: 'red' | 'ink';
  /** Decorative uses (the sign-in page) are hidden from assistive technology. */
  decorative?: boolean;
};

/**
 * The drawn side view of the curtain-sider van (docs/design/README.md section 7.1).
 * All colours come from design tokens; the lines use `ink`.
 */
export function VanSide({ label, width = 240, accent = 'red', decorative = false }: VanSideProps) {
  const t = useTranslations('vehicle');
  const accentFill = accent === 'red' ? 'var(--red)' : 'var(--ink)';
  const line = 'var(--ink)';
  return (
    <svg
      viewBox="0 0 240 112"
      width={width}
      style={{ maxWidth: '100%', height: 'auto', display: 'block' }}
      {...(decorative
        ? { 'aria-hidden': true }
        : { role: 'img', 'aria-label': t('vanAriaLabel', { label }) })}
    >
      <ellipse cx="122" cy="104" rx="112" ry="5" fill={line} opacity="0.08" />
      <rect
        x="6"
        y="10"
        width="152"
        height="70"
        rx="5"
        fill="var(--well)"
        stroke={line}
        strokeWidth="1.6"
      />
      <g stroke="var(--line)" strokeWidth="1.2">
        <path d="M18 13V77M30 13V77M42 13V77M54 13V77M66 13V77M78 13V77M90 13V77M102 13V77M114 13V77M126 13V77M138 13V77M150 13V77" />
      </g>
      <rect x="6" y="58" width="152" height="7" fill={accentFill} />
      <rect
        x="14"
        y="20"
        width="62"
        height="18"
        rx="4"
        fill="var(--surface)"
        stroke="var(--line-strong)"
      />
      <text
        x="45"
        y="33"
        textAnchor="middle"
        fontSize="11"
        fontWeight="600"
        fill={line}
        className="font-mono"
      >
        {label}
      </text>
      <rect x="6" y="80" width="154" height="6" rx="2" fill={line} />
      <path
        d="M158 28H197C204 28 209 31 213 37L226 56C228.5 59.5 230 63 230 67V84H158Z"
        fill="var(--surface)"
        stroke={line}
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path
        d="M199 34C203 34 206 36 208.5 39.5L217 54H199Z"
        fill="var(--window)"
        stroke={line}
        strokeWidth="1.2"
        strokeLinejoin="round"
      />
      <rect
        x="168"
        y="35"
        width="25"
        height="19"
        rx="2.5"
        fill="var(--window)"
        stroke={line}
        strokeWidth="1.2"
      />
      <path d="M166 58V80M196 58V80" stroke="var(--line-strong)" strokeWidth="1.2" />
      <rect x="186" y="62" width="7" height="2.5" rx="1" fill={line} />
      <rect
        x="224"
        y="64"
        width="6"
        height="7"
        rx="1.5"
        fill="var(--rest-hatch-a)"
        stroke={line}
        strokeWidth="1"
      />
      <rect x="156" y="82" width="76" height="7" rx="3" fill={line} />
      <rect x="206" y="40" width="5" height="10" rx="1.5" fill={line} />
      <circle cx="46" cy="90" r="13" fill={line} />
      <circle cx="46" cy="90" r="5.5" fill="var(--neutral-data)" />
      <circle cx="194" cy="90" r="13" fill={line} />
      <circle cx="194" cy="90" r="5.5" fill="var(--neutral-data)" />
    </svg>
  );
}
