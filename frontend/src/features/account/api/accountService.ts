import { z } from 'zod';
import {
  AccountSchema,
  AthleteClaimsResponseSchema,
  ContributionsResponseSchema,
  FavoritesSchema,
} from '../../../lib/schemas/account';
import type { Account, Favorites } from '../../../lib/schemas/account';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

async function authorizedFetch<T>(
  endpoint: string,
  accessToken: string,
  schema?: z.ZodType<T>,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
      ...init.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API protegida falló (${response.status})`);
  }

  if (response.status === 204 || !schema) {
    return null as T;
  }

  const data = await response.json();
  return schema.parse(data);
}

export const accountService = {
  getMe(accessToken: string): Promise<Account> {
    return authorizedFetch('/api/me', accessToken, AccountSchema);
  },

  getFavorites(accessToken: string): Promise<Favorites> {
    return authorizedFetch('/api/me/favorites', accessToken, FavoritesSchema);
  },

  addAthleteFavorite(accessToken: string, athleteId: string | number): Promise<void> {
    return authorizedFetch(`/api/me/favorites/athletes/${athleteId}`, accessToken, undefined, { method: 'POST' });
  },

  removeAthleteFavorite(accessToken: string, athleteId: string | number): Promise<void> {
    return authorizedFetch(`/api/me/favorites/athletes/${athleteId}`, accessToken, undefined, { method: 'DELETE' });
  },

  addClubFavorite(accessToken: string, clubId: string | number): Promise<void> {
    return authorizedFetch(`/api/me/favorites/clubs/${clubId}`, accessToken, undefined, { method: 'POST' });
  },

  removeClubFavorite(accessToken: string, clubId: string | number): Promise<void> {
    return authorizedFetch(`/api/me/favorites/clubs/${clubId}`, accessToken, undefined, { method: 'DELETE' });
  },

  listClaims(accessToken: string) {
    return authorizedFetch('/api/me/athlete-claims', accessToken, AthleteClaimsResponseSchema);
  },

  createClaim(
    accessToken: string,
    payload: {
      athlete_id: string | number;
      evidence_message: string;
      declared_club_name?: string;
      contact_hint?: string;
    },
  ) {
    return authorizedFetch('/api/me/athlete-claims', accessToken, undefined, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  listContributions(accessToken: string) {
    return authorizedFetch('/api/me/contributions', accessToken, ContributionsResponseSchema);
  },

  createContribution(
    accessToken: string,
    payload: {
      athlete_id?: string | number;
      club_id?: string | number;
      contribution_type: 'athlete_profile' | 'club_profile' | 'result_correction' | 'other';
      payload: Record<string, unknown>;
    },
  ) {
    return authorizedFetch('/api/me/contributions', accessToken, undefined, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
};
