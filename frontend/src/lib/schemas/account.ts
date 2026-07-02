import { z } from 'zod';
import { AthleteSchema } from './athlete';
import { ClubSchema } from './club';

export const AccountSchema = z.object({
  id: z.union([z.string(), z.number()]),
  email: z.string(),
  status: z.string(),
  person_id: z.union([z.string(), z.number()]),
  roles: z.array(z.object({
    id: z.union([z.string(), z.number()]),
    club_id: z.union([z.string(), z.number()]).nullable().optional(),
    role: z.string(),
  })).optional(),
});

export type Account = z.infer<typeof AccountSchema>;

export const FavoritesSchema = z.object({
  athletes: z.array(AthleteSchema.extend({ created_at: z.string().optional() })),
  clubs: z.array(ClubSchema.extend({ created_at: z.string().optional() })),
});

export type Favorites = z.infer<typeof FavoritesSchema>;

export const AthleteClaimSchema = z.object({
  id: z.union([z.string(), z.number()]),
  athlete_id: z.union([z.string(), z.number()]),
  athlete_name: z.string().optional(),
  status: z.enum(['pending', 'approved', 'rejected']),
  evidence_message: z.string().optional(),
  declared_club_name: z.string().nullable().optional(),
  contact_hint: z.string().nullable().optional(),
  review_notes: z.string().nullable().optional(),
  created_at: z.string().optional(),
  reviewed_at: z.string().nullable().optional(),
});

export const AthleteClaimsResponseSchema = z.object({
  data: z.array(AthleteClaimSchema),
});

export type AthleteClaim = z.infer<typeof AthleteClaimSchema>;

export const ContributionSchema = z.object({
  id: z.union([z.string(), z.number()]),
  athlete_id: z.union([z.string(), z.number()]).nullable().optional(),
  club_id: z.union([z.string(), z.number()]).nullable().optional(),
  contribution_type: z.string(),
  payload: z.record(z.string(), z.unknown()),
  status: z.enum(['pending', 'accepted', 'rejected']),
  review_notes: z.string().nullable().optional(),
  created_at: z.string().optional(),
  reviewed_at: z.string().nullable().optional(),
});

export const ContributionsResponseSchema = z.object({
  data: z.array(ContributionSchema),
});

export type Contribution = z.infer<typeof ContributionSchema>;
