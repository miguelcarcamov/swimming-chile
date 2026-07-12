import { lazy } from 'react';

export const LazyAthletesPage = lazy(() =>
  import('../features/athletes/pages/AthletesPage').then((m) => ({ default: m.AthletesPage }))
);
export const LazyAthleteProfilePage = lazy(() =>
  import('../features/athletes/pages/AthleteProfilePage').then((m) => ({ default: m.AthleteProfilePage }))
);
export const LazyClubsPage = lazy(() =>
  import('../features/clubs/pages/ClubsPage').then((m) => ({ default: m.ClubsPage }))
);
export const LazyClubProfilePage = lazy(() =>
  import('../features/clubs/pages/ClubProfilePage').then((m) => ({ default: m.ClubProfilePage }))
);
export const LazyCompetitionsPage = lazy(() =>
  import('../features/competitions/pages/CompetitionsPage').then((m) => ({ default: m.CompetitionsPage }))
);
export const LazyCompetitionProfilePage = lazy(() =>
  import('../features/competitions/pages/CompetitionProfilePage').then((m) => ({
    default: m.CompetitionProfilePage,
  }))
);
export const LazyRelaysPage = lazy(() =>
  import('../features/relays/pages/RelaysPage').then((m) => ({ default: m.RelaysPage }))
);
export const LazyRankingsPage = lazy(() =>
  import('../features/rankings/pages/RankingsPage').then((m) => ({ default: m.RankingsPage }))
);
