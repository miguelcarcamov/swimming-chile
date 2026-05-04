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
              {athlete.club_name && (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-emerald-50 text-emerald-700 border border-emerald-100">
                  Club actual: {athlete.club_name}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Recent Results */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 mb-4 px-1">Resultados Recientes</h2>
        
        {!athlete.recent_results || athlete.recent_results.length === 0 ? (
          <EmptyState title="Sin resultados" description="Este atleta no tiene tiempos registrados aún." />
        ) : (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-slate-50 text-slate-600 font-medium border-b border-slate-200">
                  <tr>
                    <th className="px-6 py-4">Prueba</th>
                    <th className="px-6 py-4">Competencia</th>
                    <th className="px-6 py-4">Tiempo</th>
                    <th className="px-6 py-4 text-center">Puntos</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {athlete.recent_results.map((result) => (
                    <tr key={result.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="px-6 py-4 font-medium text-slate-900">
                        {result.distance_m}m <span className="capitalize">{result.stroke}</span>
                        <span className="ml-2 text-xs uppercase bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">{result.course_type}</span>
                      </td>
                      <td className="px-6 py-4 text-slate-600">
                        {result.competition_name}
                      </td>
                      <td className="px-6 py-4">
                        <span className="font-mono text-blue-700 font-semibold">{result.result_time_text}</span>
                        {result.status !== 'valid' && (
                          <span className="ml-2 text-xs text-red-600 uppercase">({result.status})</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-center text-slate-500">
                        {result.points ? result.points : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
