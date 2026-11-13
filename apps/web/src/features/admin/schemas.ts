import { z } from 'zod';

type Translate = (key: string) => string;

/** The admin generate form (FR-30): every field is optional except the offer count. */
export function generateSchema(t: Translate) {
  return z.object({
    seed: z
      .string()
      .trim()
      .refine((value) => value === '' || /^-?\d{1,15}$/.test(value), t('seedInvalid')),
    referenceDate: z
      .string()
      .trim()
      .refine((value) => value === '' || /^\d{4}-\d{2}-\d{2}$/.test(value), t('dateInvalid')),
    offers: z
      .string()
      .trim()
      .refine(
        (value) => /^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= 500,
        t('offersRange'),
      ),
  });
}

export type GenerateValues = z.infer<ReturnType<typeof generateSchema>>;

/**
 * What the generate and reset endpoints return (FEAT-002 section 6.7). The OpenAPI document types
 * the answer as a free object, so the counts are read through this schema; anything else is shown
 * as an unknown answer instead of guessed numbers.
 */
export const demoCountsSchema = z.object({
  drivers: z.number(),
  vehicles: z.number(),
  offers: z.object({
    imported: z.number(),
    updated: z.number(),
    unchanged: z.number(),
    failed: z.number(),
  }),
});

export type DemoCounts = z.infer<typeof demoCountsSchema>;

export function parseCounts(value: unknown): DemoCounts | null {
  const parsed = demoCountsSchema.safeParse(value);
  return parsed.success ? parsed.data : null;
}
