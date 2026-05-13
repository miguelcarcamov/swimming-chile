import { AthletesResponseSchema, AthleteProfileSchema } from '../../../lib/schemas/athlete';
import type { AthletesResponse, AthleteProfile } from '../../../lib/schemas/athlete';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export interface SearchAthletesParams {
  query?: string;
  club_id?: string;
  gender?: string;
  page?: number;
}

export const athleteService = {
  async searchAthletes(params: SearchAthletesParams = {}): Promise<AthletesResponse> {
    const url = new URL(`${API_BASE_URL}/api/athletes`);
    if (params.query) url.searchParams.append('search', params.query);
    if (params.club_id) url.searchParams.append('club_id', params.club_id);
    if (params.gender && params.gender !== 'all') url.searchParams.append('gender', params.gender);
    url.searchParams.append('page', (params.page || 1).toString());
    
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch athletes');
    
    const data = await response.json();
    return AthletesResponseSchema.parse(data);
  },

  async getAthleteProfile(id: string): Promise<AthleteProfile> {
    const response = await fetch(`${API_BASE_URL}/api/athletes/${id}`);
    if (!response.ok) throw new Error('Failed to fetch athlete profile');
    
    const data = await response.json();
    return AthleteProfileSchema.parse(data);
  }
};
