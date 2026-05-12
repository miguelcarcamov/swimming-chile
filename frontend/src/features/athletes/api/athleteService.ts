import { AthletesResponseSchema, AthleteProfileSchema } from '../../../lib/schemas/athlete';
import type { AthletesResponse, AthleteProfile } from '../../../lib/schemas/athlete';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export const athleteService = {
  async searchAthletes(query: string = '', page: number = 1): Promise<AthletesResponse> {
    const url = new URL(`${API_BASE_URL}/api/athletes`);
    if (query) url.searchParams.append('search', query);
    url.searchParams.append('page', page.toString());
    
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
