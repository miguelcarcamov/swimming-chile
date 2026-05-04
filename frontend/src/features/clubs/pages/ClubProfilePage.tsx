import React from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { clubService } from '../api/clubService';
import { athleteService } from '../../athletes/api/athleteService';
import { LoadingState } from '../../../components/ui/LoadingState';
import { ErrorState } from '../../../components/ui/ErrorState';
import { EmptyState } from '../../../components/ui/EmptyState';

export const ClubProfilePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // Fetch Club details (en un escenario real habría un getClubById, por ahora buscamos en la lista)
  const { data: clubsResponse, isLoading: loadingClub } = useQuery({
    queryKey: ['clubs'],
    queryFn: () => clubService.getClubs(),
  });

  const club = clubsResponse?.data.find(c => c.id === id);

  // Fetch Athletes for this club (mockeamos trayendo todos y filtrando)
  const { data: athletesResponse, isLoading: loadingAthletes } = useQuery({
    queryKey: ['athletes-by-club', id],
    queryFn: () => athleteService.searchAthletes(''),
  });

  const clubAthletes = athletesResponse?.data.filter(a => a.club_name === club?.name);

  if (loadingClub || loadingAthletes) return <LoadingState />;
  if (!club) return <EmptyState title="Club no encontrado" />;

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="mb-6">
        <button 
          onClick={() => navigate(-1)}
          className="text-sm font-medium text-blue-600 hover:text-blue-800 flex items-center gap-1 cursor-pointer bg-transparent border-none p-0"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Volver atrás
        </button>
      </div>

      {/* Header Club */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 md:p-8">
        <div className="flex flex-col md:flex-row gap-6 items-start md:items-center">
          <div className="w-20 h-20 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center font-bold text-4xl shadow-sm flex-shrink-0">
            {club.name.charAt(0)}
          </div>
          <div>
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">{club.name}</h1>
            <div className="mt-2 flex flex-wrap gap-3">
              <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-slate-100 text-slate-700 border border-slate-200">
                <svg className="w-4 h-4 mr-1 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                {club.city}, {club.country}
              </span>
              <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-emerald-50 text-emerald-700 border border-emerald-100">
                {club.total_athletes || 0} Nadadores registrados
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Atletas del Club */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 mb-4 px-1">Atletas del Club</h2>
        
        {!clubAthletes || clubAthletes.length === 0 ? (
          <EmptyState title="Sin atletas" description="No hemos encontrado atletas asociados a este club." />
        ) : (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <ul className="divide-y divide-slate-200">
              {clubAthletes.map((athlete) => (
                <li key={athlete.id} className="hover:bg-slate-50 transition-colors">
                  <Link to={`/athletes/${athlete.id}`} className="block p-4 sm:px-6">
                    <div className="flex items-center justify-between">
                      <div className="flex flex-col">
                        <p className="text-sm font-semibold text-blue-600 truncate">{athlete.full_name}</p>
                        <p className="text-sm text-slate-500 mt-1 flex items-center gap-2">
                          <span className="capitalize">{athlete.gender}</span>
                          {athlete.birth_year && (
                            <>
                              <span>&bull;</span>
                              <span>Nacido en {athlete.birth_year}</span>
                            </>
                          )}
                        </p>
                      </div>
                      <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};
