import { z } from 'zod';

type Translate = (key: string) => string;

const isNumber = (value: string) => value.trim() !== '' && Number.isFinite(Number(value));

/** A number typed into a text field: required, finite and inside [min, max]. */
function numberIn(t: Translate, min: number, max: number, rangeKey: string, integer = false) {
  return z
    .string()
    .trim()
    .min(1, t('numberRequired'))
    .refine(isNumber, t('numberRequired'))
    .refine((value) => Number(value) >= min && Number(value) <= max, t(rangeKey))
    .refine((value) => !integer || Number.isInteger(Number(value)), t(rangeKey));
}

/** Empty, or a coordinate inside [min, max]. */
const optionalCoordinate = (t: Translate, min: number, max: number, key: string) =>
  z
    .string()
    .trim()
    .refine(
      (value) => value === '' || (isNumber(value) && Number(value) >= min && Number(value) <= max),
      {
        message: t(key),
      },
    );

function stopSchema(t: Translate) {
  return z
    .object({
      city: z.string().trim().min(1, t('cityRequired')).max(120, t('cityRequired')),
      countryCode: z
        .string()
        .trim()
        .regex(/^[A-Z]{2}$/, t('countryInvalid')),
      lat: optionalCoordinate(t, -90, 90, 'latitudeRange'),
      lon: optionalCoordinate(t, -180, 180, 'longitudeRange'),
      windowStart: z.string().min(1, t('dateRequired')),
      windowEnd: z.string().min(1, t('dateRequired')),
      serviceMinutes: z
        .string()
        .trim()
        .refine(
          (value) =>
            value === '' ||
            (isNumber(value) && Number.isInteger(Number(value)) && Number(value) >= 0),
          {
            message: t('serviceInvalid'),
          },
        ),
    })
    .refine((stop) => !stop.windowStart || !stop.windowEnd || stop.windowEnd > stop.windowStart, {
      path: ['windowEnd'],
      message: t('windowOrder'),
    })
    .refine((stop) => (stop.lat === '') === (stop.lon === ''), {
      path: ['lon'],
      message: t('coordinatesPair'),
    });
}

/** Limits mirror FEAT-001 section 6.1: weight 1-3 500 kg, 1-33 pallets, two stops. */
export function offerSchema(t: Translate) {
  return z.object({
    description: z
      .string()
      .trim()
      .min(1, t('descriptionRequired'))
      .max(2000, t('descriptionRequired')),
    weightKg: numberIn(t, 1, 3500, 'weightRange'),
    palletType: z.enum(['EUR_1200x800', 'IND_1200x1000', 'HALF_800x600', 'UNKNOWN']),
    palletCount: numberIn(t, 1, 33, 'palletsRange', true),
    loadingLengthM: z
      .string()
      .trim()
      .refine((value) => value === '' || (isNumber(value) && Number(value) > 0), {
        message: t('lengthPositive'),
      }),
    requiredBodyTypes: z.array(z.string()).min(1, t('bodyRequired')),
    price: z
      .string()
      .trim()
      .refine((value) => value === '' || /^\d+([.,]\d{1,2})?$/.test(value), {
        message: t('priceInvalid'),
      }),
    publicRemark: z.string().trim().max(500, t('remarkTooLong')),
    loading: stopSchema(t),
    unloading: stopSchema(t),
  });
}
export type OfferFormValues = z.infer<ReturnType<typeof offerSchema>>;
