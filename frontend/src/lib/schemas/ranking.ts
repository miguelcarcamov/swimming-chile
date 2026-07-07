import { z } from 'zod';
import { PaginationMetaSchema } from './athlete';
import { EventGenderSchema, StrokeSchema, CourseTypeSchema } from './canon';

export const RankingEntrySchema = z.object({
  rank: z.number().int(),
  athlete_name: z.string(),
  athlete_id: z.union([z.string(), z.number()]),
  club_name: z.string().nullable().optional(),
  time_text: z.string(),
  time_ms: z.number().int(),
  competition_id: z.union([z.string(), z.number()]),
  competition_name: z.string(),
  date: z.string().nullable().optional(),
  distance_m: z.number().int(),
  stroke: StrokeSchema,
  course_type: CourseTypeSchema.nullable().optional(),
  gender: EventGenderSchema,
  age_group: z.string(),
  event_age_group: z.string(),
  birth_year: z.number().int().nullable().optional(),
  current_age: z.number().int().nullable().optional(),
});

export type RankingEntry = z.infer<typeof RankingEntrySchema>;

export const RankingsResponseSchema = z.object({
  data: z.array(RankingEntrySchema),
  meta: PaginationMetaSchema,
});

export type RankingsResponse = z.infer<typeof RankingsResponseSchema>;

export const RankingFilterOptionsSchema = z.object({
  distances: z.array(z.number().int()),
  strokes: z.array(StrokeSchema),
  event_options: z.array(z.object({
    distance_m: z.number().int(),
    stroke: StrokeSchema,
  })),
  age_groups: z.array(z.string()),
  years: z.array(z.number().int()),
  scopes: z.array(z.string()),
});

export type RankingFilterOptions = z.infer<typeof RankingFilterOptionsSchema>;

export const ClubParticipationEntrySchema = z.object({
  rank: z.number().int(),
  club_id: z.union([z.string(), z.number()]),
  club_name: z.string(),
  unique_athletes: z.number().int(),
  competitions_count: z.number().int(),
  entries_count: z.number().int(),
});

export type ClubParticipationEntry = z.infer<typeof ClubParticipationEntrySchema>;

export const ClubParticipationResponseSchema = z.object({
  data: z.array(ClubParticipationEntrySchema),
  meta: PaginationMetaSchema,
});

export type ClubParticipationResponse = z.infer<typeof ClubParticipationResponseSchema>;
