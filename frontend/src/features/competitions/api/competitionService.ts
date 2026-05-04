import { CompetitionsResponseSchema, CompetitionDetailResponseSchema } from '../../../lib/schemas/competition';
import type { CompetitionsResponse, CompetitionDetailResponse } from '../../../lib/schemas/competition';
import fixtureData from '../../../test/fixtures/competitions.json';
import fixtureDetail from '../../../test/fixtures/competition_results.json';

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export const competitionService = {
  async getCompetitions(): Promise<CompetitionsResponse> {
    await delay(500);

    const allData = fixtureData.search_results as CompetitionsResponse;
    
    const parsed = CompetitionsResponseSchema.safeParse(allData);
    if (!parsed.success) {
      throw new Error("Fixture data invalid: " + parsed.error.message);
    }

    return parsed.data;
  },

  async getCompetitionDetail(id: string): Promise<CompetitionDetailResponse> {
    await delay(700);

    // Mock logic: si el id no existe en los datos genéricos, lanzamos error (simulando 404)
    const exists = fixtureData.search_results.data.some(c => c.id === id);
    if (!exists) throw new Error("Competition not found");

    const detailData = fixtureDetail as CompetitionDetailResponse;

    // Sustituir el metadata mockeado con el id solicitado para mayor realismo en UI
    const mockResponse = {
      competition: { ...detailData.competition, id },
      events: detailData.events
    };

    const parsed = CompetitionDetailResponseSchema.safeParse(mockResponse);
    if (!parsed.success) {
      throw new Error("Fixture data invalid: " + parsed.error.message);
    }

    return parsed.data;
  }
};
