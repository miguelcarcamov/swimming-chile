import { z } from 'zod';
import { PaginationMetaSchema } from './athlete';
import { CourseTypeSchema } from './canon';

export const CompetitionSchema = z.object({
  id: z.union([z.string(), z.number()]),
  name: z.string(),
  date_start: z.string(),
  date_end: z.string().nullable().optional(),
  location: z.string().nullable().optional(),
  course_type: CourseTypeSchema.nullable().optional(),
  competition_scope: z.string().nullable().optional(),
  governing_body_code: z.string().nullable().optional(),
  governing_body_name: z.string().nullable().optional(),
  organizer: z.string().nullable().optional(),
  source_url: z.string().nullable().optional(),
});

export type Competition = z.infer<typeof CompetitionSchema>;

export const CompetitionsResponseSchema = z.object({
  data: z.array(CompetitionSchema),
  meta: PaginationMetaSchema,
});

export type CompetitionsResponse = z.infer<typeof CompetitionsResponseSchema>;

export const CompetitionFilterOptionsSchema = z.object({
  years: z.array(z.number().int()),
  scopes: z.array(z.string()),
  governing_bodies: z.array(z.object({
    governing_body_code: z.string(),
    governing_body_name: z.string().nullable().optional(),
  })),
});

export type CompetitionFilterOptions = z.infer<typeof CompetitionFilterOptionsSchema>;

import { EventGenderSchema, StrokeSchema, ResultStatusSchema } from './canon';

export const CompetitionResultSchema = z.object({
  rank: z.number().int().nullable().optional(),
  athlete_name: z.string(),
  athlete_id: z.union([z.string(), z.number()]).nullable().optional(),
  club_name: z.string().nullable().optional(),
  time_text: z.string(),
  seed_time_text: z.string().nullable().optional(),
  seed_time_ms: z.number().int().nullable().optional(),
  result_time_ms: z.number().int().nullable().optional(),
  status: ResultStatusSchema,
});

export type CompetitionResult = z.infer<typeof CompetitionResultSchema>;

export const CompetitionEventSchema = z.object({
  id: z.union([z.string(), z.number()]),
  distance_m: z.number().int(),
  stroke: StrokeSchema,
  gender: EventGenderSchema,
  age_group: z.string(),
  results: z.array(CompetitionResultSchema),
});

export type CompetitionEvent = z.infer<typeof CompetitionEventSchema>;

export const CompetitionDetailResponseSchema = z.object({
  competition: CompetitionSchema,
  events: z.array(CompetitionEventSchema),
});

export type CompetitionDetailResponse = z.infer<typeof CompetitionDetailResponseSchema>;

export const CompetitionStatsSchema = z.object({
  participants_count: z.number().int(),
  women_count: z.number().int(),
  men_count: z.number().int(),
  clubs_count: z.number().int(),
  dsq_count: z.number().int(),
  valid_results_count: z.number().int(),
  entries_count: z.number().int(),
  events_count: z.number().int(),
});

export type CompetitionStats = z.infer<typeof CompetitionStatsSchema>;
