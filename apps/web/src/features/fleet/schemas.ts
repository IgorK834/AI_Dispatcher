import { z } from 'zod';

type Translate = (key: string) => string;

/** A number typed into a text field: required, finite and inside [min, max]. */
function numberIn(t: Translate, min: number, max: number, rangeKey: string) {
  return z
    .string()
    .trim()
    .min(1, t('numberRequired'))
    .refine((value) => Number.isFinite(Number(value)), t('numberRequired'))
    .refine((value) => Number(value) >= min && Number(value) <= max, t(rangeKey));
}

/** An optional number above zero: empty is allowed. */
function optionalPositive(t: Translate) {
  return z
    .string()
    .trim()
    .refine((value) => value === '' || (Number.isFinite(Number(value)) && Number(value) > 0), {
      message: t('dimensionPositive'),
    });
}

/** Limits mirror the API schemas (DriverCreate in contracts/openapi.json). */
export function driverSchema(t: Translate) {
  return z.object({
    name: z.string().trim().min(1, t('nameRequired')).max(120, t('nameTooLong')),
    phone: z.string().trim().max(80, t('phoneTooLong')),
    homeCity: z.string().trim().min(1, t('cityRequired')),
    homeCountry: z
      .string()
      .trim()
      .regex(/^[A-Z]{2}$/, t('countryInvalid')),
    homeLat: numberIn(t, -90, 90, 'latitudeRange'),
    homeLon: numberIn(t, -180, 180, 'longitudeRange'),
    defaultRulesProfile: z.enum(['pl_domestic_employee_v1', 'eu561_van_international_v1']),
    vehicleId: z.string(),
  });
}
export type DriverFormValues = z.infer<ReturnType<typeof driverSchema>>;

/** Limits mirror VehicleCreate: payload 100-2 000 kg, gross weight up to 3 500 kg, 1-12 places. */
export function vehicleSchema(t: Translate) {
  return z.object({
    label: z.string().trim().min(1, t('labelRequired')).max(120, t('labelTooLong')),
    bodyType: z.enum(['CURTAIN_SIDER', 'TAUTLINER', 'BOX']),
    palletPlaces: numberIn(t, 1, 12, 'placesRange').refine(
      (value) => Number.isInteger(Number(value)),
      t('placesRange'),
    ),
    layoutTemplate: z.enum(['EUR_MIXED_6X4', 'EUR_MIXED_5X3', 'DECLARED_ONLY']),
    sideAccess: z.enum(['LEFT', 'RIGHT', 'BOTH', 'NONE']),
    payloadKg: numberIn(t, 100, 2000, 'payloadRange'),
    gvwKg: numberIn(t, 1, 3500, 'gvwRange'),
    sleeperCab: z.boolean(),
    fuelEmpty: numberIn(t, 0.01, 1000, 'fuelPositive'),
    fuelFull: numberIn(t, 0.01, 1000, 'fuelPositive'),
    costProfileId: z.string().min(1, t('costProfileRequired')),
    innerLengthM: optionalPositive(t),
    innerWidthM: optionalPositive(t),
    innerHeightM: optionalPositive(t),
  });
}
export type VehicleFormValues = z.infer<ReturnType<typeof vehicleSchema>>;

const minutes = (t: Translate) => numberIn(t, 0, 100000, 'minutesRange');

/** DriverStateCreate: counters are minutes of zero or more. */
export function stateSchema(t: Translate) {
  return z.object({
    availableFrom: z.string().min(1, t('dateRequired')),
    currentCity: z.string().trim(),
    currentLat: numberIn(t, -90, 90, 'latitudeRange'),
    currentLon: numberIn(t, -180, 180, 'longitudeRange'),
    workTodayMin: minutes(t),
    driveTodayMin: minutes(t),
    workSinceBreakMin: minutes(t),
    driveSinceBreakMin: minutes(t),
    workWeekMin: minutes(t),
    driveWeekMin: minutes(t),
    drivePrevWeekMin: minutes(t),
    homeBy: z.string(),
  });
}
export type StateFormValues = z.infer<ReturnType<typeof stateSchema>>;
