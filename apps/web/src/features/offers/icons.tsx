/** Line icons (1.4 px stroke, currentColor, hidden from assistive technology). */
const props = {
  width: 15,
  height: 15,
  viewBox: '0 0 16 16',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.4,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
} as const;

export const EditIcon = () => (
  <svg {...props}>
    <path d="M10.5 2.5 13.5 5.5 5.5 13.5H2.5V10.5L10.5 2.5Z" />
  </svg>
);

export const TrashIcon = () => (
  <svg {...props}>
    <path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.6 8.5h5.8l.6-8.5" />
  </svg>
);

export const PlusIcon = () => (
  <svg {...props}>
    <path d="M8 3v10M3 8h10" />
  </svg>
);

export const InfoIcon = () => (
  <svg {...props}>
    <circle cx="8" cy="8" r="5.5" />
    <path d="M8 7.2V11M8 5v.2" />
  </svg>
);

export const LockIcon = () => (
  <svg {...props}>
    <rect x="3.5" y="7" width="9" height="6.5" rx="1.5" />
    <path d="M5.5 7V5.2a2.5 2.5 0 0 1 5 0V7" />
  </svg>
);
