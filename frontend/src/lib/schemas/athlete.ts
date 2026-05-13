import { z } from 'zod';
import { AthleteGenderSchema, StrokeSchema, ResultStatusSchema, CourseTypeSchema } from './canon';

// Base Athlete
export const AthleteSchema = z.object({
  id: z.union([z.string(), z.number()]),
  full_name: z.string(),
  gender: AthleteGenderSchema.nullable().optional(),
  birth_year: z.number().int().nullable().optional(),
  club_name: z.string().nullable().optional(),
});

export type Athlete = z.infer<typeof AthleteSchema>;

// Athlete Result (Individual)
export const AthleteResultSchema = z.object({
  id: z.union([z.string(), z.number()]),
  event_name: z.string().nullable().optional(),
  stroke: StrokeSchema.nullable().optional(),
  distance_m: z.number().int().nullable().optional(),
  course_type: CourseTypeSchema.nullable().optional(),
  age_group: z.string().nullable().optional(),
  competition_name: z.string(),
  competition_date: z.string().nullable().optional(),
  result_time_text: z.string().nullable().optional(),
  result_time_ms: z.number().int().nullable().optional(),
  points: z.coerce.number().nullable().optional(),
  rank_position: z.number().int().nullable().optional(),
  status: ResultStatusSchema.nullable().optional(),
});

export type AthleteResult = z.infer<typeof AthleteResultSchema>;

// Athlete Details (Profile with Results)
export const AthleteProfileSchema = AthleteSchema.extend({
  recent_results: z.array(AthleteResultSchema).optional(),
});

export type AthleteProfile = z.infer<typeof AthleteProfileSchema>;

// Pagination Meta
export const PaginationMetaSchema = z.object({
  total_results: z.number().int(),
  page: z.number().int(),
  page_size: z.number().int(),
  total_pages: z.number().int(),
});

export type PaginationMeta = z.infer<typeof PaginationMetaSchema>;

// API Responses
export const AthletesResponseSchema = z.object({
  data: z.array(AthleteSchema),
  meta: PaginationMetaSchema,
});

export type AthletesResponse = z.infer<typeof AthletesResponseSchema>;
