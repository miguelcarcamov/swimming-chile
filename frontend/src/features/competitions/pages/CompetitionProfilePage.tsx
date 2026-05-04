import React, { useState, useMemo } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { competitionService } from '../api/competitionService';
import { LoadingState } from '../../../components/ui/LoadingState';
import { ErrorState } from '../../../components/ui/ErrorState';
import { EmptyState } from '../../../components/ui/EmptyState';
import type { CompetitionEvent } from '../../../lib/schemas/competition';

const strokeTranslations: Record<string, string> = {
  freestyle: 'Libre',
  backstroke: 'Espalda',
  breaststroke: 'Pecho',
  butterfly: 'Mariposa',
  individual_medley: 'Combinado',
  medley_relay: 'Relevo Combinado',
  freestyle_relay: 'Relevo Libre',
};

const genderTranslations: Record<string, string> = {
  women: 'Damas',
  men: 'Varones',
  mixed: 'Mixto',
};

// Componente local para cada Prueba (Colapsable)
const EventCard: React.FC<{ event: CompetitionEvent; eventTitle: string; isSearching: boolean }> = ({ event, eventTitle, isSearching }) => {
  const [expanded, setExpanded] = useState(false);
  const showContent = isSearching || expanded;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div 
        className="bg-slate-50 border-b border-slate-200 px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 cursor-pointer hover:bg-slate-100 transition-colors select-none"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <svg className={`w-5 h-5 text-slate-400 transition-transform ${showContent ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
          <h3 className="text-lg font-bold text-slate-900">{eventTitle}</h3>
        </div>
        <div className="flex items-center gap-3">
           <span className="text-sm text-slate-500 font-medium">{event.results.length} nadadores</span>
           <span className="text-xs font-mono font-medium text-slate-500 bg-slate-200 px-2 py-1 rounded hidden sm:inline-block">ID: {event.id.split('-')[0]}</span>
        </div>
      </div>
      
      {showContent && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-white text-slate-500 font-medium border-b border-slate-100">
              <tr>
                <th className="px-6 py-3 w-16 text-center">Pos</th>
                <th className="px-6 py-3">Nadador</th>
                <th className="px-6 py-3 hidden sm:table-cell">Club</th>
                <th className="px-6 py-3 text-right">Tiempo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {event.results.map((result, idx) => (
                <tr key={`${result.athlete_id}-${idx}`} className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-3 text-center">
                    {result.rank ? (
                      <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full font-bold text-xs ${
                        result.rank === 1 ? 'bg-amber-100 text-amber-700' :
                        result.rank === 2 ? 'bg-slate-100 text-slate-600' :
                        result.rank === 3 ? 'bg-orange-50 text-orange-700' :
                        'text-slate-500'
                      }`}>
                        {result.rank}
                      </span>
                    ) : (
                      <span className="text-slate-400 font-bold">-</span>
                    )}
                  </td>
                  <td className="px-6 py-3">
                    <Link to={`/athletes/${result.athlete_id}`} className="font-semibold text-blue-600 hover:text-blue-800 hover:underline" onClick={(e) => e.stopPropagation()}>
                      {result.athlete_name}
                    </Link>
                    <div className="text-xs text-slate-500 sm:hidden mt-0.5">{result.club_name}</div>
                  </td>
                  <td className="px-6 py-3 text-slate-600 hidden sm:table-cell">{result.club_name}</td>
                  <td className="px-6 py-3 text-right">
                    {result.status === 'valid' ? (
                      <span className="font-mono font-bold text-slate-900">{result.time_text}</span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-50 text-red-700 uppercase">
                        {result.status}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export const CompetitionProfilePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [genderFilter, setGenderFilter] = useState('all');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['competition-detail', id],
    queryFn: () => competitionService.getCompetitionDetail(id!),
    enabled: !!id,
    retry: false,
  });

  const filteredEvents = useMemo(() => {
    if (!data) return [];
    
    return data.events.map(event => {
      if (genderFilter !== 'all' && event.gender !== genderFilter) return null;
      
      const eventTitle = `${event.distance_m}m ${strokeTranslations[event.stroke]} ${genderTranslations[event.gender]} - ${event.age_group} años`;
      const query = searchQuery.toLowerCase().trim();
      
      if (!query) return { ...event, eventTitle };

      const matchesEventTitle = eventTitle.toLowerCase().includes(query);
      
      const matchingResults = event.results.filter(r => 
        r.athlete_name.toLowerCase().includes(query) ||
        r.club_name.toLowerCase().includes(query)
      );
      
      if (!matchesEventTitle && matchingResults.length === 0) return null;
      
      return {
        ...event,
        eventTitle,
        results: matchesEventTitle ? event.results : matchingResults
      };
    }).filter(Boolean) as (CompetitionEvent & { eventTitle: string })[];
  }, [data, searchQuery, genderFilter]);

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <EmptyState title="Competencia no encontrada" description="La competencia que buscas no existe o fue removida." />;

  const { competition } = data;
  const dateObj = new Date(competition.date_start);
  const formattedDate = dateObj.toLocaleDateString('es-CL', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  const isSearching = searchQuery.trim().length > 0;

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

      {/* Header Competencia */}
      <div className="bg-slate-900 rounded-2xl shadow-xl p-6 md:p-8 text-white relative overflow-hidden">
        <div className="absolute top-0 right-0 -mt-8 -mr-8 w-48 h-48 bg-blue-600 rounded-full opacity-20 blur-3xl pointer-events-none"></div>
        
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider bg-blue-500/20 text-blue-300 border border-blue-500/30">
                Piscina {competition.course_type === 'scm' ? 'Corta (25m)' : 'Larga (50m)'}
              </span>
            </div>
            <h1 className="text-3xl md:text-4xl font-black tracking-tight mb-2">{competition.name}</h1>
            <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-6 text-slate-300 text-sm">
              <span className="flex items-center gap-1.5">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                <span className="capitalize">{formattedDate}</span>
              </span>
              <span className="flex items-center gap-1.5">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                {competition.location || 'Sede por confirmar'}
              </span>
            </div>
          </div>
          
          <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4 text-center min-w-32 border border-white/10 shadow-inner">
            <span className="block text-3xl font-black text-white leading-none">{data.events.length}</span>
            <span className="text-xs font-medium text-slate-300 uppercase tracking-widest mt-1 block">Pruebas Totales</span>
          </div>
        </div>
      </div>

      {/* Buscador y Filtros */}
      <div className="bg-white p-4 rounded-xl shadow-sm border border-slate-200 flex flex-col md:flex-row gap-4">
        <div className="relative flex-1">
          <input
            type="text"
            className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-shadow outline-none bg-white text-sm"
            placeholder="Buscar por prueba (ej: 50m Libre), nombre de atleta o club..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <svg className="w-5 h-5 text-slate-400 absolute left-3 top-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
        
        <div className="flex w-full md:w-auto">
          <select 
            value={genderFilter} 
            onChange={(e) => setGenderFilter(e.target.value)}
            className="w-full md:w-48 py-2 pl-3 pr-8 border border-slate-300 bg-white rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
          >
            <option value="all">Ambos Géneros</option>
            <option value="women">Damas</option>
            <option value="men">Varones</option>
            <option value="mixed">Mixtos</option>
          </select>
        </div>
      </div>

      {/* Resultados por Evento */}
      <div className="space-y-4">
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight mb-6">Resultados</h2>
        
        {filteredEvents.length === 0 ? (
          <EmptyState 
            title="No se encontraron resultados" 
            description={isSearching ? "Intenta con otros términos de búsqueda." : "No hay resultados cargados para esta competencia."} 
          />
        ) : (
          <div className="flex flex-col gap-4">
            {filteredEvents.map((event) => (
              <EventCard 
                key={event.id} 
                event={event} 
                eventTitle={event.eventTitle} 
                isSearching={isSearching} 
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
