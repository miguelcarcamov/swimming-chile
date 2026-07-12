import { Suspense, type ReactNode } from 'react';
import { createBrowserRouter } from 'react-router-dom';
import { MainLayout } from '../components/layout/MainLayout';
import { LoadingState } from '../components/ui/LoadingState';
import { HomePage } from '../features/home/pages/HomePage';
import {
  LazyAthleteProfilePage,
  LazyAthletesPage,
  LazyClubProfilePage,
  LazyClubsPage,
  LazyCompetitionProfilePage,
  LazyCompetitionsPage,
  LazyRankingsPage,
  LazyRelaysPage,
} from './lazyPages';

function withSuspense(element: ReactNode) {
  return <Suspense fallback={<LoadingState />}>{element}</Suspense>;
}

export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      {
        index: true,
        element: <HomePage />,
      },
      {
        path: 'athletes',
        element: withSuspense(<LazyAthletesPage />),
      },
      {
        path: 'athletes/:id',
        element: withSuspense(<LazyAthleteProfilePage />),
      },
      {
        path: 'clubs',
        element: withSuspense(<LazyClubsPage />),
      },
      {
        path: 'clubs/:id',
        element: withSuspense(<LazyClubProfilePage />),
      },
      {
        path: 'calendar',
        element: withSuspense(<LazyCompetitionsPage mode="upcoming" />),
      },
      {
        path: 'competitions',
        element: withSuspense(<LazyCompetitionsPage mode="past" />),
      },
      {
        path: 'competitions/:id',
        element: withSuspense(<LazyCompetitionProfilePage />),
      },
      {
        path: 'relays',
        element: withSuspense(<LazyRelaysPage />),
      },
      {
        path: 'rankings',
        element: withSuspense(<LazyRankingsPage />),
      },
    ],
  },
]);
