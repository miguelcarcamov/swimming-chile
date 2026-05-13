import { z } from 'zod';

// Canon de datos derivado estrictamente de backend/docs/schema.md

export const EventGenderSchema = z.enum(['women', 'men', 'mixed']);
export type EventGender = z.infer<typeof EventGenderSchema>;

export const AthleteGenderSchema = z.enum(['female', 'male']);
export type AthleteGender = z.infer<typeof AthleteGenderSchema>;

export const StrokeSchema = z.enum([
  'freestyle',
  'backstroke',
  'breaststroke',
  'butterfly',
  'individual_medley',
  'medley_relay',
  'freestyle_relay',
]);
export type Stroke = z.infer<typeof StrokeSchema>;

export const ResultStatusSchema = z.enum([
  'valid',
  'dns',
  'dnf',
  'dsq',
  'scratch',
  'unknown',
]);
export type ResultStatus = z.infer<typeof ResultStatusSchema>;

export const CourseTypeSchema = z.enum(['scm', 'lcm', 'owy', 'unknown']);
export type CourseType = z.infer<typeof CourseTypeSchema>;
