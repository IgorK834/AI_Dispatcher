'use client';

import { useTranslations } from 'next-intl';
import { useState, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';

type ComposerProps = {
  busy: boolean;
  onSend: (content: string) => void;
};

const MAX_LENGTH = 2000;

/** The message input; disabled until the run finishes (FR-21). */
export function Composer({ busy, onSend }: ComposerProps) {
  const t = useTranslations('chat.composer');
  const [value, setValue] = useState('');
  const content = value.trim();

  function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || content === '') return;
    onSend(content);
    setValue('');
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <label htmlFor="chat-message" className="text-sm font-semibold text-ink">
        {t('label')}
      </label>
      <div className="flex flex-wrap items-end gap-3">
        <textarea
          id="chat-message"
          rows={2}
          maxLength={MAX_LENGTH}
          value={value}
          disabled={busy}
          aria-describedby="chat-message-hint"
          placeholder={t('placeholder')}
          onChange={(event) => setValue(event.target.value)}
          className="min-h-11 min-w-0 flex-1 rounded-control border border-line-strong bg-surface px-3 py-2 text-ink disabled:bg-well disabled:text-ink3"
        />
        <Button type="submit" variant="primary" disabled={busy || content === ''}>
          {t('send')}
        </Button>
      </div>
      <p id="chat-message-hint" className="text-xs text-ink3">
        {t('hint')}
      </p>
    </form>
  );
}
