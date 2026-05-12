import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { athleteService } from '../api/athleteService';
import { LoadingState } from '../../../components/ui/LoadingState';
import { ErrorState } from '../../../components/ui/ErrorState';
import { EmptyState } from '../../../components/ui/EmptyState';

export const AthletesPage: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [page, setPage] = useState(1);

  // Sincronización simple de debouncing para no saturar llamadas
  React.useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedQuery(searchTerm);
      setPage(1); // Resetear página a 1 cada vez que se busca algo nuevo
    }, 400);
    return () => clearTimeout(handler);
  }, [searchTerm]);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['athletes', debouncedQuery, page],
    queryFn: () => athleteService.searchAthletes(debouncedQuery, page),
  });

  return (
    <div className="space-y-6">
      {/* Header & Search */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Atletas</h1>
          <p className="text-slate-500 mt-1">Busca nadadores y revisa su historial competitivo.</p>
        </div>
        <div className="relative w-full md:w-96">
          <input
            type="text"
            placeholder="Buscar por nombre (ej. Perez, Juan)..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-shadow outline-none bg-white"
          />
          <svg className="w-5 h-5 text-slate-400 absolute left-3 top-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
      </div>

      {/* States */}
      {isLoading && <LoadingState />}
      {isError && <ErrorState onRetry={() => refetch()} />}
      
      {/* List */}
      {!isLoading && !isError && data && (
        <>
          {data.data.length === 0 ? (
            <EmptyState 
              title="No se encontraron atletas" 
              description={`No hay coincidencias para "${debouncedQuery}". Intenta con otro nombre.`} 
            />
          ) : (
            <div className="space-y-4">
              <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <ul className="divide-y divide-slate-200">
                  {data.data.map((athlete) => (
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
                          <div className="flex items-center gap-4">
                            {athlete.club_name && (
                              <span className="hidden md:inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800">
                                {athlete.club_name}
                              </span>
                            )}
                            <svg className="w-5 h-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                          </div>
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Paginación */}
              <div className="flex items-center justify-between border-t border-slate-200 pt-4">
                <p className="text-sm text-slate-500">
                  Mostrando página {data.meta.page} de {data.meta.total_pages} ({data.meta.total_results} resultados)
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={data.meta.page === 1}
                    className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium text-slate-700 bg-white hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    Anterior
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(data.meta.total_pages, p + 1))}
                    disabled={data.meta.page >= data.meta.total_pages}
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
  );
};
