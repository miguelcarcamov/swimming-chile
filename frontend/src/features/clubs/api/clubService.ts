import { ClubsResponseSchema, ClubSchema } from '../../../lib/schemas/club';
import type { ClubsResponse, Club } from '../../../lib/schemas/club';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export const clubService = {
  async getClubs(query: string = '', page: number = 1, sort: 'athletes' | 'name' = 'athletes'): Promise<ClubsResponse> {
    const url = new URL(`${API_BASE_URL}/api/clubs`);
    if (query) url.searchParams.append('search', query);
    url.searchParams.append('sort', sort);
    url.searchParams.append('page', page.toString());
    
    const response = await fetch(url);
    if (!response.ok) throw new Error('Failed to fetch clubs');
    
    const data = await response.json();
    return ClubsResponseSchema.parse(data);
  },

  async getClubProfile(id: string): Promise<Club> {
    const response = await fetch(`${API_BASE_URL}/api/clubs/${id}`);
    if (!response.ok) throw new Error('Failed to fetch club profile');
    
    const data = await response.json();
    return ClubSchema.parse(data);
  }
};
