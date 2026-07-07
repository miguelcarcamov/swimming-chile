import {
  ClubParticipationResponseSchema,
  RankingFilterOptionsSchema,
  RankingsResponseSchema,
} from '../../../lib/schemas/ranking';
import type {
  ClubParticipationResponse,
  RankingFilterOptions,
  RankingsResponse,
} from '../../../lib/schemas/ranking';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export type RankingQuery = {
  distance_m?: string;
  stroke?: string;
  gender?: string;
  age_group?: string;
  course_type?: string;
  year?: string;
  competition_scope?: string;
  athlete_search?: string;
  page?: number;
};

function appendFilter(url: URL, key: string, value?: string) {
  if (value && value !== 'all') {
    url.searchParams.append(key, value);
  }
}

export const rankingService = {
  async getRankings(query: RankingQuery = {}): Promise<RankingsResponse> {
    const url = new URL(`${API_BASE_URL}/api/rankings`);
    appendFilter(url, 'distance_m', query.distance_m);
    appendFilter(url, 'stroke', query.stroke);
    appendFilter(url, 'gender', query.gender);
    appendFilter(url, 'age_group', query.age_group);
    appendFilter(url, 'course_type', query.course_type);
    appendFilter(url, 'year', query.year);
    appendFilter(url, 'competition_scope', query.competition_scope);
    appendFilter(url, 'athlete_search', query.athlete_search);
    url.searchParams.append('page', String(query.page || 1));

    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch rankings');

    const data = await response.json();
    return RankingsResponseSchema.parse(data);
  },

  async getFilterOptions(): Promise<RankingFilterOptions> {
    const response = await fetch(`${API_BASE_URL}/api/rankings/filter-options`);
    if (!response.ok) throw new Error('Failed to fetch ranking filter options');

    const data = await response.json();
    return RankingFilterOptionsSchema.parse(data);
  },

  async getClubParticipation(page: number = 1): Promise<ClubParticipationResponse> {
    const url = new URL(`${API_BASE_URL}/api/stats/clubs/participation`);
    url.searchParams.append('page', String(page));

    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch club participation stats');

    const data = await response.json();
    return ClubParticipationResponseSchema.parse(data);
  }
};
