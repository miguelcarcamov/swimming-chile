import { CompetitionDetailResponseSchema, CompetitionFilterOptionsSchema, CompetitionStatsSchema, CompetitionsResponseSchema } from '../../../lib/schemas/competition';
import type { CompetitionDetailResponse, CompetitionFilterOptions, CompetitionStats, CompetitionsResponse } from '../../../lib/schemas/competition';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export const competitionService = {
  async getCompetitions(
    query: string = '',
    year: string = 'all',
    page: number = 1,
    timeframe: string = 'all',
    competitionScope: string = 'all',
    governingBody: string = 'all'
  ): Promise<CompetitionsResponse> {
    const url = new URL(`${API_BASE_URL}/api/competitions`);
    if (query) url.searchParams.append('search', query);
    if (year !== 'all') url.searchParams.append('year', year);
    if (timeframe !== 'all') url.searchParams.append('timeframe', timeframe);
    if (competitionScope !== 'all') url.searchParams.append('competition_scope', competitionScope);
    if (governingBody !== 'all') url.searchParams.append('governing_body', governingBody);
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

  async getCompetitionStats(id: string): Promise<CompetitionStats> {
    const response = await fetch(`${API_BASE_URL}/api/competitions/${id}/stats`);
    if (!response.ok) throw new Error('Failed to fetch competition stats');

    const data = await response.json();
    return CompetitionStatsSchema.parse(data);
  },

  async getCompetitionYears(): Promise<number[]> {
    const response = await fetch(`${API_BASE_URL}/api/competitions/years`);
    if (!response.ok) throw new Error('Failed to fetch competition years');
    const data = await response.json();
    return data.years;
  },

  async getCompetitionFilterOptions(timeframe: string = 'all'): Promise<CompetitionFilterOptions> {
    const url = new URL(`${API_BASE_URL}/api/competitions/filter-options`);
    if (timeframe !== 'all') url.searchParams.append('timeframe', timeframe);

    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch competition filter options');
    const data = await response.json();
    return CompetitionFilterOptionsSchema.parse(data);
  }
};
