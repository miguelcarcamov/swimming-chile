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

  // Estados para filtros de atletas
  const [searchTerm, setSearchTerm] = React.useState('');
  const [debouncedQuery, setDebouncedQuery] = React.useState('');
  const [gender, setGender] = React.useState('all');
  const [page, setPage] = React.useState(1);

  React.useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedQuery(searchTerm);
      setPage(1);
    }, 400);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  React.useEffect(() => {
    setPage(1);
  }, [gender]);

  // Fetch Club details
  const { data: club, isLoading: loadingClub, isError: errorClub, refetch: refetchClub } = useQuery({
    queryKey: ['club-profile', id],
    queryFn: () => clubService.getClubProfile(id!),
    enabled: !!id,
  });

  // Fetch paginated athletes for this club
  const { data: athletesData, isLoading: loadingAthletes, isError: errorAthletes, refetch: refetchAthletes } = useQuery({
    queryKey: ['athletes', debouncedQuery, id, gender, page],
    queryFn: () => athleteService.searchAthletes({ 
      query: debouncedQuery, 
      club_id: id, 
      gender, 
      page 
    }),
    enabled: !!id,
  });

  if (loadingClub) return <LoadingState />;
  if (errorClub) return <ErrorState onRetry={() => refetchClub()} />;
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
                {club.city || 'Desconocido'}, {club.country || 'Chile'}
              </span>
              <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-emerald-50 text-emerald-700 border border-emerald-100">
                {club.total_athletes || 0} Nadadores registrados
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Filtros de Atletas */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 mb-4 px-1">Atletas del Club</h2>
        
        <div className="flex flex-col md:flex-row gap-4 mb-6">
          <div className="relative w-full md:w-96">
            <input
              type="text"
              className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-shadow outline-none bg-white text-sm"
              placeholder="Buscar nadador..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
            <svg className="w-5 h-5 text-slate-400 absolute left-3 top-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          
          <select
            value={gender}
            onChange={(e) => setGender(e.target.value)}
            className="px-4 py-2 border border-slate-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white text-sm text-slate-700 cursor-pointer"
          >
            <option value="all">Todos los géneros</option>
            <option value="female">Damas</option>
            <option value="male">Varones</option>
          </select>
        </div>

        {/* Lista de Atletas Paginada */}
        {loadingAthletes && <LoadingState />}
        {errorAthletes && <ErrorState onRetry={() => refetchAthletes()} />}
        
        {!loadingAthletes && !errorAthletes && athletesData && (
          <>
            {athletesData.data.length === 0 ? (
              <EmptyState title="Sin atletas" description="No hemos encontrado atletas con esos filtros." />
            ) : (
              <div className="space-y-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {athletesData.data.map((athlete) => (
                    <Link 
                      key={athlete.id} 
                      to={`/athletes/${athlete.id}`}
                      className="group bg-white rounded-xl shadow-sm border border-slate-200 p-5 hover:shadow-md hover:border-blue-300 transition-all flex items-center justify-between"
                    >
                      <div>
                        <p className="font-semibold text-slate-900 group-hover:text-blue-700 transition-colors">{athlete.full_name}</p>
                        <p className="text-sm text-slate-500 mt-1 flex items-center gap-2">
                          <span className="capitalize">{athlete.gender === 'female' ? 'Dama' : 'Varón'}</span>
                          {athlete.birth_year && (
                            <>
                              <span>&bull;</span>
                              <span>Nacido {athlete.birth_year}</span>
                            </>
                          )}
                        </p>
                      </div>
                      <div className="w-10 h-10 rounded-full bg-slate-50 flex items-center justify-center text-slate-400 group-hover:bg-blue-50 group-hover:text-blue-600 transition-colors">
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </div>
                    </Link>
                  ))}
                </div>

                {/* Paginación */}
                <div className="flex items-center justify-between border-t border-slate-200 pt-4">
                  <p className="text-sm text-slate-500">
                    Mostrando página {athletesData.meta.page} de {athletesData.meta.total_pages} ({athletesData.meta.total_results} atletas)
                  </p>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={athletesData.meta.page === 1}
                      className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      Anterior
                    </button>
                    <button
                      onClick={() => setPage((p) => Math.min(athletesData.meta.total_pages, p + 1))}
                      disabled={athletesData.meta.page >= athletesData.meta.total_pages}
                      className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      Siguiente
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
