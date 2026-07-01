import { RelayAnalysisResponseSchema } from '../../../lib/schemas/relay';
import type { RelayAnalysisResponse } from '../../../lib/schemas/relay';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export const relayService = {
  async getClubRoster(clubId: string, relayType: string): Promise<RelayAnalysisResponse> {
    const url = new URL(`${API_BASE_URL}/api/relays/club-roster`);
    url.searchParams.set('club_id', clubId);
    url.searchParams.set('relay_type', relayType);

    const response = await fetch(url);
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail ?? 'No se pudo cargar el roster del club');
    }

    const data = await response.json();
    return RelayAnalysisResponseSchema.parse(data);
  },

  async getClubRosterFromAttendance(clubId: string, relayType: string, file: File): Promise<RelayAnalysisResponse> {
    const url = new URL(`${API_BASE_URL}/api/relays/club-roster`);
    url.searchParams.set('club_id', clubId);
    url.searchParams.set('relay_type', relayType);

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/octet-stream',
      },
      body: file,
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail ?? 'No se pudo filtrar asistentes desde el Excel');
    }

    const data = await response.json();
    return RelayAnalysisResponseSchema.parse(data);
  },

  async analyzeEntries(
    relayType: string,
    options: { file?: File; clubId?: string; athleteIds?: string[] } = {},
  ): Promise<RelayAnalysisResponse> {
    const url = new URL(`${API_BASE_URL}/api/relays/analyze`);
    url.searchParams.set('filename', options.file?.name ?? 'attendance.xlsx');
    url.searchParams.set('relay_type', relayType);
    if (options.clubId) url.searchParams.set('club_id', options.clubId);
    for (const athleteId of options.athleteIds ?? []) url.searchParams.append('athlete_ids', athleteId);

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/octet-stream',
      },
      body: options.file ?? new Blob([]),
    });

    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail ?? 'No se pudo analizar la planilla de asistencia');
    }

    const data = await response.json();
    return RelayAnalysisResponseSchema.parse(data);
  },
};
