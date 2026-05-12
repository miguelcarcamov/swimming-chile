import { z } from 'zod';
import { PaginationMetaSchema } from './athlete';

export const ClubSchema = z.object({
  id: z.union([z.string(), z.number()]),
  name: z.string(),
  city: z.string().nullable().optional(),
  country: z.string().nullable().optional(),
  total_athletes: z.number().int().nullable().optional(),
});

export type Club = z.infer<typeof ClubSchema>;

export const ClubsResponseSchema = z.object({
  data: z.array(ClubSchema),
  meta: PaginationMetaSchema,
});

export type ClubsResponse = z.infer<typeof ClubsResponseSchema>;

import { AthleteSchema } from './athlete';

export const ClubProfileSchema = z.object({
  club: ClubSchema,
  athletes: z.array(AthleteSchema),
});

export type ClubProfile = z.infer<typeof ClubProfileSchema>;
