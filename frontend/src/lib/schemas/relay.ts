import { z } from 'zod';

export const RelayStrokeKeySchema = z.enum(['backstroke', 'breaststroke', 'butterfly', 'freestyle']);
export type RelayStrokeKey = z.infer<typeof RelayStrokeKeySchema>;

export const RelayTimeSchema = z.object({
  ms: z.number().int().nullable(),
  text: z.string().nullable(),
  source: z.enum(['db', 'excel', 'missing', 'manual']),
  competition_name: z.string().nullable().optional(),
  competition_date: z.string().nullable().optional(),
});

export const RelayAthleteSchema = z.object({
  id: z.string(),
  core_athlete_id: z.number().int().nullable(),
  full_name: z.string(),
  gender: z.enum(['female', 'male', 'unknown']),
  birth_date: z.string().nullable(),
  birth_year: z.number().int().nullable(),
  age: z.number().int().nullable(),
  rut: z.string().nullable(),
  times: z.record(RelayStrokeKeySchema, RelayTimeSchema),
});
export type RelayAthlete = z.infer<typeof RelayAthleteSchema>;

export const RelaySlotSchema = z.object({
  key: z.string(),
  label: z.string(),
  leg_order: z.number().int(),
  stroke: RelayStrokeKeySchema,
  stroke_label: z.string(),
});
export type RelaySlot = z.infer<typeof RelaySlotSchema>;

export const RelayTypeSchema = z.object({
  key: z.string(),
  label: z.string(),
  distance_m: z.number().int().optional(),
  style: z.string().optional(),
  gender_rule: z.string(),
  slots: z.array(RelaySlotSchema),
});
export type RelayType = z.infer<typeof RelayTypeSchema>;

export const RelayLegSchema = z.object({
  slot_key: z.string(),
  slot_label: z.string(),
  leg_order: z.number().int(),
  stroke: RelayStrokeKeySchema,
  stroke_label: z.string(),
  athlete_id: z.string().nullable(),
  athlete_name: z.string().nullable(),
  gender: z.enum(['female', 'male', 'unknown']).nullable(),
  age: z.number().int().nullable(),
  time_ms: z.number().int().nullable(),
  time_text: z.string().nullable(),
  time_source: z.enum(['db', 'excel', 'missing', 'manual']).nullable(),
});
export type RelayLeg = z.infer<typeof RelayLegSchema>;

export const RelayValidationSchema = z.object({
  is_valid: z.boolean(),
  category_key: z.string().nullable(),
  category_label: z.string().nullable(),
  age_sum: z.number().int().nullable(),
  total_time_ms: z.number().int().nullable(),
  total_time_text: z.string().nullable(),
  errors: z.array(z.string()),
  warnings: z.array(z.string()),
});
export type RelayValidation = z.infer<typeof RelayValidationSchema>;

export const RelayLineupSchema = z.object({
  id: z.string(),
  relay_type: z.string(),
  category_key: z.string().nullable(),
  category_label: z.string().nullable(),
  age_sum: z.number().int().nullable(),
  total_time_ms: z.number().int().nullable(),
  total_time_text: z.string().nullable(),
  legs: z.array(RelayLegSchema),
  validation: RelayValidationSchema,
});
export type RelayLineup = z.infer<typeof RelayLineupSchema>;

export const RelayCategorySchema = z.object({
  key: z.string(),
  label: z.string(),
  min_age_sum: z.number().int(),
  max_age_sum: z.number().int(),
});
export type RelayCategory = z.infer<typeof RelayCategorySchema>;

export const RelayStrokeSchema = z.object({
  key: RelayStrokeKeySchema,
  label: z.string(),
});
export type RelayStroke = z.infer<typeof RelayStrokeSchema>;

export const RelayAnalysisResponseSchema = z.object({
  competition_year: z.number().int(),
  relay_type: RelayTypeSchema,
  relay_types: z.array(RelayTypeSchema),
  relay_event: z.string(),
  strokes: z.array(RelayStrokeSchema),
  categories: z.array(RelayCategorySchema),
  athletes: z.array(RelayAthleteSchema),
  proposal: z.array(RelayLineupSchema),
  alternatives: z.record(z.string(), z.array(RelayLineupSchema)),
  unassigned_athlete_ids: z.array(z.string()),
});
export type RelayAnalysisResponse = z.infer<typeof RelayAnalysisResponseSchema>;
