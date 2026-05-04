import { createBrowserRouter } from 'react-router-dom';
import { MainLayout } from '../components/layout/MainLayout';

// Páginas
import { AthletesPage } from '../features/athletes/pages/AthletesPage';
import { AthleteProfilePage } from '../features/athletes/pages/AthleteProfilePage';
import { ClubsPage } from '../features/clubs/pages/ClubsPage';
import { ClubProfilePage } from '../features/clubs/pages/ClubProfilePage';
import { CompetitionsPage } from '../features/competitions/pages/CompetitionsPage';
import { CompetitionProfilePage } from '../features/competitions/pages/CompetitionProfilePage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      {
        index: true,
        element: <AthletesPage />,
      },
      {
        path: 'athletes/:id',
        element: <AthleteProfilePage />,
      },
      {
        path: 'clubs',
        element: <ClubsPage />,
      },
      {
        path: 'clubs/:id',
        element: <ClubProfilePage />,
      },
      {
        path: 'competitions',
        element: <CompetitionsPage />,
      },
      {
        path: 'competitions/:id',
        element: <CompetitionProfilePage />,
      },
    ],
  },
]);
