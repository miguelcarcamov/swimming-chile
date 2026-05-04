import { z } from 'zod';
import { PaginationMetaSchema } from './athlete';
import { CourseTypeSchema } from './canon';

export const CompetitionSchema = z.object({
  id: z.string().uuid(),
  name: z.string(),
  date_start: z.string().datetime(),
  date_end: z.string().datetime().optional(),
  location: z.string().optional(),
  course_type: CourseTypeSchema,
});

export type Competition = z.infer<typeof CompetitionSchema>;

export const CompetitionsResponseSchema = z.object({
  data: z.array(CompetitionSchema),
  meta: PaginationMetaSchema,
});

export type CompetitionsResponse = z.infer<typeof CompetitionsResponseSchema>;

import { EventGenderSchema, StrokeSchema, ResultStatusSchema } from './canon';

export const CompetitionResultSchema = z.object({
  rank: z.number().int().optional(),
  athlete_name: z.string(),
  athlete_id: z.string().uuid(),
  club_name: z.string(),
  time_text: z.string(),
  status: ResultStatusSchema,
});

export type CompetitionResult = z.infer<typeof CompetitionResultSchema>;

export const CompetitionEventSchema = z.object({
  id: z.string().uuid(),
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
