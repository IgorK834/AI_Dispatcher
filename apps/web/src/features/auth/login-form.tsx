'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { Turnstile, type TurnstileInstance } from '@marsidev/react-turnstile';
import { useQuery } from '@tanstack/react-query';
import { useLocale, useTranslations } from 'next-intl';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Banner } from '@/components/ui/banner';
import { Button } from '@/components/ui/button';
import { Field, Input } from '@/components/ui/field';
import { api } from '@/lib/api/client';
import { toProblem } from '@/lib/api/errors';
import { safeNextPath } from './next-path';
import { useSession } from './session';

const captchaConfig = z.object({ siteKey: z.string() });

type FormValues = { email: string; password: string };

/** The three failures of FR-4 get their own message; anything else uses the generic mapping. */
type Failure = { code: string; message: string; requestId?: string };

export function LoginForm({ showLocalHint }: { showLocalHint: boolean }) {
  const t = useTranslations('auth');
  const errors = useTranslations('errors');
  const locale = useLocale();
  const router = useRouter();
  const search = useSearchParams();
  const { signedIn } = useSession();
  const widget = useRef<TurnstileInstance | undefined>(undefined);
  const [token, setToken] = useState<string | null>(null);
  const [resets, setResets] = useState(0);
  const [failure, setFailure] = useState<Failure | null>(null);

  const schema = useMemo(
    () =>
      z.object({
        email: z
          .string()
          .min(1, t('validation.emailRequired'))
          .pipe(z.email(t('validation.emailInvalid'))),
        password: z.string().min(1, t('validation.passwordRequired')),
      }),
    [t],
  );
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    mode: 'onBlur',
    defaultValues: { email: '', password: '' },
  });

  const captcha = useQuery({
    queryKey: ['captcha-config'],
    queryFn: async () => {
      const { data } = await api.GET('/api/v1/auth/captcha-config', {});
      return captchaConfig.parse(data);
    },
    staleTime: Infinity,
    retry: false,
  });

  async function submit(values: FormValues) {
    if (!token) return;
    setFailure(null);
    const { data, error, response } = await api.POST('/api/v1/auth/login', {
      body: { email: values.email, password: values.password, captchaToken: token },
    });
    if (data) {
      signedIn(data.user, data.csrfToken);
      router.replace(safeNextPath(search.get('next')));
      return;
    }
    const problem = toProblem(error, errors);
    // The password never survives a failed attempt; the email stays.
    form.setValue('password', '');
    if (problem.code === 'CAPTCHA_FAILED') {
      setResets((count) => count + 1); // the effect below resets the widget
      setToken(null);
    }
    if (problem.code === 'RATE_LIMITED') {
      const seconds = Number(response.headers.get('Retry-After'));
      setFailure({
        code: problem.code,
        requestId: problem.requestId,
        message: t('rateLimited', {
          seconds: Number.isFinite(seconds) && seconds > 0 ? seconds : 30,
        }),
      });
      return;
    }
    setFailure({ code: problem.code, message: problem.message, requestId: problem.requestId });
  }

  useEffect(() => {
    if (resets > 0) widget.current?.reset();
  }, [resets]);

  const submitting = form.formState.isSubmitting;
  return (
    <form
      noValidate
      onSubmit={form.handleSubmit(submit)}
      className="flex flex-col gap-4"
      aria-label={t('title')}
    >
      <Field id="login-email" label={t('form.email')} error={form.formState.errors.email?.message}>
        {(control) => (
          <Input {...control} type="email" autoComplete="username" {...form.register('email')} />
        )}
      </Field>
      <Field
        id="login-password"
        label={t('form.password')}
        error={form.formState.errors.password?.message}
      >
        {(control) => (
          <Input
            {...control}
            type="password"
            autoComplete="current-password"
            {...form.register('password')}
          />
        )}
      </Field>

      <div className="flex flex-col gap-2 rounded-inner bg-well p-3">
        <span className="text-xs text-ink3">{t('form.captchaHint')}</span>
        {captcha.isError ? (
          <Banner level="error">{t('form.captchaUnavailable')}</Banner>
        ) : captcha.data ? (
          <Turnstile
            ref={widget}
            siteKey={captcha.data.siteKey}
            options={{ language: locale === 'pl' ? 'pl' : 'en' }}
            onSuccess={setToken}
            onExpire={() => setToken(null)}
            onError={() => setToken(null)}
          />
        ) : (
          <span className="text-xs text-ink3">{t('form.captchaLoading')}</span>
        )}
      </div>

      {failure && (
        <Banner level={failure.code === 'RATE_LIMITED' ? 'attention' : 'error'}>
          {failure.message}
        </Banner>
      )}

      <Button type="submit" variant="primary" disabled={!token} loading={submitting}>
        {submitting ? t('form.submitting') : t('form.submit')}
      </Button>

      {showLocalHint && (
        <Banner level="info" title={t('localHint.title')}>
          {t('localHint.body', { demo: 'demo@example.invalid', admin: 'admin@example.invalid' })}
        </Banner>
      )}
    </form>
  );
}
