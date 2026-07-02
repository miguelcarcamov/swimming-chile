import { createBrowserRouter } from 'react-router-dom';
import { MainLayout } from '../components/layout/MainLayout';

// Páginas
import { AthletesPage } from '../features/athletes/pages/AthletesPage';
import { AthleteProfilePage } from '../features/athletes/pages/AthleteProfilePage';
import { ClubsPage } from '../features/clubs/pages/ClubsPage';
import { ClubProfilePage } from '../features/clubs/pages/ClubProfilePage';
import { CompetitionsPage } from '../features/competitions/pages/CompetitionsPage';
import { CompetitionProfilePage } from '../features/competitions/pages/CompetitionProfilePage';
import { RelaysPage } from '../features/relays/pages/RelaysPage';
import { AccountPage } from '../features/account/pages/AccountPage';
import { HomePage } from '../features/home/pages/HomePage';

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
        path: 'calendar',
        element: <CompetitionsPage mode="upcoming" />,
      },
      {
        path: 'competitions',
        element: <CompetitionsPage mode="past" />,
      },
      {
        path: 'competitions/:id',
        element: <CompetitionProfilePage />,
      },
      {
        path: 'relays',
        element: <RelaysPage />,
      },
      {
        path: 'account',
        element: <AccountPage />,
      },
    ],
  },
]);
