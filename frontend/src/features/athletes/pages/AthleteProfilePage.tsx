import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { athleteService } from '../api/athleteService';
import { LoadingState } from '../../../components/ui/LoadingState';
import { ErrorState } from '../../../components/ui/ErrorState';
import { EmptyState } from '../../../components/ui/EmptyState';

export const AthleteProfilePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: athlete, isLoading, isError, refetch } = useQuery({
    queryKey: ['athlete', id],
    queryFn: () => athleteService.getAthleteProfile(id!),
    enabled: !!id,
  });

  const { pbs, groupedRecent } = React.useMemo(() => {
    if (!athlete || !athlete.recent_results) return { pbs: [], groupedRecent: {} };
    
    // PBs
    const bests = new Map<string, typeof athlete.recent_results[0]>();
    athlete.recent_results.forEach(res => {
      if (res.status !== 'valid' || !res.result_time_ms) return;
      const key = `${res.distance_m}-${res.stroke}-${res.course_type}`;
      if (!bests.has(key) || res.result_time_ms < bests.get(key)!.result_time_ms!) {
        bests.set(key, res);
      }
    });
    
    const pbArray = Array.from(bests.values()).sort((a, b) => {
      if (a.stroke !== b.stroke) return (a.stroke || '').localeCompare(b.stroke || '');
      if (a.distance_m !== b.distance_m) return (a.distance_m || 0) - (b.distance_m || 0);
      return (a.course_type || '').localeCompare(b.course_type || '');
    });

    // Grouping by Competition
    const grouped = athlete.recent_results.reduce((acc, res) => {
      if (!acc[res.competition_name]) acc[res.competition_name] = [];
      acc[res.competition_name].push(res);
      return acc;
    }, {} as Record<string, typeof athlete.recent_results>);
    
    return { pbs: pbArray, groupedRecent: grouped };
  }, [athlete]);

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState onRetry={() => refetch()} />;
  if (!athlete) return <EmptyState title="Atleta no encontrado" />;



  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Breadcrumb / Back button */}
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

      {/* Header Profile */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 md:p-8">
        <div className="flex flex-col md:flex-row gap-6 items-start md:items-center">
          <div className="w-20 h-20 bg-gradient-to-br from-slate-200 to-slate-300 rounded-full flex items-center justify-center text-slate-500 shadow-inner flex-shrink-0">
            <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
          <div>
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">{athlete.full_name}</h1>
            <div className="mt-2 flex flex-wrap gap-3">
              <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-50 text-blue-700 border border-blue-100 capitalize">
                {athlete.gender}
              </span>
              {athlete.birth_year && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-slate-100 text-slate-700 border border-slate-200">
                  Año de nacimiento: {athlete.birth_year}
                </span>
              )}
              {(athlete.current_club_name || athlete.club_name) && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-emerald-50 text-emerald-700 border border-emerald-100">
                  Club vigente: {athlete.current_club_name || athlete.club_name}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Mejores Tiempos */}
      {pbs.length > 0 && (
        <div>
          <h2 className="text-xl font-bold text-slate-900 mb-4 px-1">Mejores Tiempos</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {pbs.map(res => (
              <div key={res.id} className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 flex items-center justify-between">
                <div>
                  <div className="font-bold text-slate-900">{res.distance_m}m <span className="capitalize">{res.stroke}</span></div>
                  <div className="text-xs text-slate-500 uppercase flex items-center gap-2 mt-0.5 tracking-wider">
                    <span>{res.course_type}</span>
                    {res.age_group && (
                      <>
                        <span className="w-1 h-1 rounded-full bg-slate-300"></span>
                        <span className="tracking-wide">Cat: {res.age_group}</span>
                      </>
                    )}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-blue-700 font-bold text-lg">{res.result_time_text}</div>
                  <div className="text-xs text-slate-500 truncate max-w-[120px]" title={res.competition_name}>{res.competition_name}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Results */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 mb-4 px-1 mt-8">Historial de Resultados</h2>
        
        {!athlete.recent_results || athlete.recent_results.length === 0 ? (
          <EmptyState title="Sin resultados" description="Este atleta no tiene tiempos registrados aún." />
        ) : (
          <div className="space-y-6">
            {Object.entries(groupedRecent).map(([compName, results]) => (
              <div key={compName} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="bg-slate-50 border-b border-slate-200 px-4 py-3">
                  <h3 className="font-bold text-slate-800">{compName}</h3>
                </div>
                <div className="divide-y divide-slate-100">
                  {results.map(res => (
                    <div key={res.id} className="px-4 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-slate-50/50 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center text-blue-700 font-bold text-sm shrink-0">
                          {res.rank_position ? `${res.rank_position}°` : '-'}
                        </div>
                        <div>
                          <div className="font-semibold text-slate-900">{res.distance_m}m <span className="capitalize">{res.stroke}</span></div>
                          <div className="text-xs text-slate-500 uppercase flex items-center gap-2">
                            <span>{res.course_type}</span>
                            {res.age_group && (
                              <>
                                <span className="w-1 h-1 rounded-full bg-slate-300"></span>
                                <span className="tracking-wide">Cat: {res.age_group}</span>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                      
                      <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-center w-full sm:w-auto mt-2 sm:mt-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-100">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-slate-900 font-semibold">{res.result_time_text}</span>
                          {res.status !== 'valid' && (
                            <span className="text-xs font-bold text-red-600 bg-red-50 px-1.5 py-0.5 rounded">{res.status}</span>
                          )}
                        </div>
                        {res.points && (
                          <div className="text-xs text-slate-500 mt-1">
                            <span className="font-semibold text-emerald-600">{res.points}</span> pts
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
