import { CompetitionsResponseSchema, CompetitionDetailResponseSchema } from '../../../lib/schemas/competition';
import type { CompetitionsResponse, CompetitionDetailResponse } from '../../../lib/schemas/competition';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export const competitionService = {
  async getCompetitions(query: string = '', year: string = 'all', page: number = 1, timeframe: string = 'all'): Promise<CompetitionsResponse> {
    const url = new URL(`${API_BASE_URL}/api/competitions`);
    if (query) url.searchParams.append('search', query);
    if (year !== 'all') url.searchParams.append('year', year);
    if (timeframe !== 'all') url.searchParams.append('timeframe', timeframe);
    url.searchParams.append('page', page.toString());
    
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch competitions');
    
    const data = await response.json();
    return CompetitionsResponseSchema.parse(data);
  },

  async getCompetitionDetail(id: string): Promise<CompetitionDetailResponse> {
    const response = await fetch(`${API_BASE_URL}/api/competitions/${id}`);
    if (!response.ok) throw new Error('Failed to fetch competition details');
    
    const data = await response.json();
    return CompetitionDetailResponseSchema.parse(data);
  },

  async getCompetitionYears(): Promise<number[]> {
    const response = await fetch(`${API_BASE_URL}/api/competitions/years`);
    if (!response.ok) throw new Error('Failed to fetch competition years');
    const data = await response.json();
    return data.years;
  }
};
