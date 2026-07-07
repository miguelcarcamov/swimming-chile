import React, { useState, useMemo } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { competitionService } from '../api/competitionService';
import { LoadingState } from '../../../components/ui/LoadingState';
import { ErrorState } from '../../../components/ui/ErrorState';
import { EmptyState } from '../../../components/ui/EmptyState';
import { CourseBadge } from '../../../components/ui/CourseBadge';
import { getCourseMeta } from '../../../lib/courseMeta';
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
const getMinAge = (ageGroup: string) => {
  const match = ageGroup.match(/\d+/);
  return match ? parseInt(match[0], 10) : 0;
};

type AgeGroupCategory = CompetitionEvent & { categoryTitle: string };

type PruebaGroup = {
  pruebaKey: string;
  pruebaTitle: string;
  distance_m: number;
  stroke: string;
  gender: string;
  ageGroups: AgeGroupCategory[];
};

const TimeComparison: React.FC<{ seedMs?: number | null; resultMs?: number | null }> = ({ seedMs, resultMs }) => {
  if (!seedMs || !resultMs) return null;

  const diffSeconds = (resultMs - seedMs) / 1000;
  if (diffSeconds === 0) {
    return <span className="text-xs font-semibold text-slate-500">±0.00s</span>;
  }

  const improved = diffSeconds < 0;

  return (
    <span className={`text-xs font-bold ${improved ? 'text-emerald-600' : 'text-red-600'}`}>
      {improved ? '' : '+'}{diffSeconds.toFixed(2)}s
    </span>
  );
};

const CategoryResults: React.FC<{ cat: AgeGroupCategory; isRelay: boolean; isSearching: boolean }> = ({ cat, isRelay, isSearching }) => {
  const [expanded, setExpanded] = useState(false);
  const showContent = isSearching || expanded;

  return (
    <div className="border-b border-slate-100 last:border-0">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 bg-slate-50/50 px-6 py-2 text-left border-b border-slate-200 hover:bg-slate-100 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <svg className={`w-4 h-4 text-slate-400 transition-transform ${showContent ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
          <h4 className="font-semibold text-slate-700 text-sm">{cat.categoryTitle}</h4>
        </div>
        <span className="text-xs font-medium text-slate-500">{cat.results.length} {isRelay ? 'equipos' : 'nadadores'}</span>
      </button>

      {showContent && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-white text-slate-500 font-medium border-b border-slate-100">
              <tr>
                <th className="px-6 py-2 w-16 text-center">Pos</th>
                <th className="px-6 py-2">{isRelay ? 'Equipo' : 'Nadador'}</th>
                <th className="px-6 py-2 hidden sm:table-cell">Club</th>
                <th className="px-6 py-2 text-right hidden md:table-cell">Seed</th>
                <th className="px-6 py-2 text-right">Tiempo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {cat.results.map((result, idx) => (
                <tr key={`${result.athlete_id || 'relay'}-${idx}`} className="hover:bg-slate-50 transition-colors">
                  <td className="px-6 py-2 text-center">
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
                  <td className="px-6 py-2">
                    {result.athlete_id ? (
                      <Link to={`/athletes/${result.athlete_id}`} className="font-semibold text-blue-600 hover:text-blue-800 hover:underline">
                        {result.athlete_name}
                      </Link>
                    ) : (
                      <span className="font-semibold text-slate-800">
                        {result.athlete_name}
                      </span>
                    )}
                    <div className="text-xs text-slate-500 sm:hidden mt-0.5">{result.club_name}</div>
                  </td>
                  <td className="px-6 py-2 text-slate-600 hidden sm:table-cell">{result.club_name}</td>
                  <td className="px-6 py-2 text-right hidden md:table-cell">
                    <span className="font-mono text-slate-500">{result.seed_time_text || '-'}</span>
                  </td>
                  <td className="px-6 py-2 text-right">
                    {result.status === 'valid' ? (
                      <div className="flex flex-col items-end">
                        <span className="font-mono font-bold text-slate-900">{result.time_text}</span>
                        <TimeComparison seedMs={result.seed_time_ms} resultMs={result.result_time_ms} />
                      </div>
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

const PruebaCard: React.FC<{ group: PruebaGroup; isSearching: boolean }> = ({ group, isSearching }) => {
  const [expanded, setExpanded] = useState(false);
  const showContent = isSearching || expanded;
  const totalParticipants = group.ageGroups.reduce((acc, cat) => acc + cat.results.length, 0);
  const isRelay = group.stroke.includes('relay');

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
          <h3 className="text-lg font-bold text-slate-900">{group.pruebaTitle}</h3>
        </div>
        <div className="flex items-center gap-3">
           <span className="text-sm text-slate-500 font-medium">{totalParticipants} {isRelay ? 'equipos' : 'nadadores'}</span>
           <span className="text-xs font-mono font-medium text-slate-500 bg-slate-200 px-2 py-1 rounded hidden sm:inline-block">{group.ageGroups.length} categorías</span>
        </div>
      </div>
      
      {showContent && (
        <div className="flex flex-col">
          {group.ageGroups.map(cat => (
            <CategoryResults key={cat.id} cat={cat} isRelay={isRelay} isSearching={isSearching} />
          ))}
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

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['competition-detail', id],
    queryFn: () => competitionService.getCompetitionDetail(id!),
    enabled: !!id,
    retry: false,
  });

  const statsQuery = useQuery({
    queryKey: ['competition-stats', id],
    queryFn: () => competitionService.getCompetitionStats(id!),
    enabled: !!id,
    retry: false,
  });

  const groupedEvents = useMemo(() => {
    if (!data) return [];
    
    const groups = new Map<string, PruebaGroup>();

    data.events.forEach(event => {
      if (genderFilter !== 'all' && event.gender !== genderFilter) return;

      const pruebaKey = `${event.distance_m}-${event.stroke}-${event.gender}`;
      const pruebaTitle = `${event.distance_m}m ${strokeTranslations[event.stroke]} ${genderTranslations[event.gender]}`;
      const categoryTitle = `Categoría: ${event.age_group} años`;

      const query = searchQuery.toLowerCase().trim();
      
      let matchingResults = event.results;
      let matchesSearch = false;

      if (query) {
        const matchesPruebaTitle = pruebaTitle.toLowerCase().includes(query);
        const matchesCategory = categoryTitle.toLowerCase().includes(query);
        
        matchingResults = event.results.filter(r => 
          r.athlete_name.toLowerCase().includes(query) ||
          (r.club_name || '').toLowerCase().includes(query)
        );

        if (matchesPruebaTitle || matchesCategory) {
          matchingResults = event.results;
          matchesSearch = true;
        } else if (matchingResults.length > 0) {
          matchesSearch = true;
        }
      } else {
        matchesSearch = true;
      }

      if (matchesSearch) {
        if (!groups.has(pruebaKey)) {
          groups.set(pruebaKey, {
            pruebaKey,
            pruebaTitle,
            distance_m: event.distance_m,
            stroke: event.stroke,
            gender: event.gender,
            ageGroups: []
          });
        }
        groups.get(pruebaKey)!.ageGroups.push({
          ...event,
          categoryTitle,
          results: matchingResults
        });
      }
    });

    return Array.from(groups.values()).map(group => {
      group.ageGroups.sort((a, b) => getMinAge(a.age_group) - getMinAge(b.age_group));
      return group;
    });
  }, [data, searchQuery, genderFilter]);

  const totalUniquePruebas = useMemo(() => {
    if (!data) return 0;
    const unique = new Set(data.events.map(e => `${e.distance_m}-${e.stroke}-${e.gender}`));
    return unique.size;
  }, [data]);

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState onRetry={() => refetch()} />;
  if (!data) return <EmptyState title="Competencia no encontrada" description="La competencia que buscas no existe o fue removida." />;

  const { competition } = data;
  // Avoid timezone shifts when the API returns a date-only value (YYYY-MM-DD).
  const dateString = competition.date_start.includes('T') ? competition.date_start : `${competition.date_start}T12:00:00`;
  const dateObj = new Date(dateString);
  const formattedDate = dateObj.toLocaleDateString('es-CL', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  const isSearching = searchQuery.trim().length > 0;
  const course = getCourseMeta(competition.course_type);
  const hasActiveFilters = searchQuery.trim() !== '' || genderFilter !== 'all';

  const clearFilters = () => {
    setSearchQuery('');
    setGenderFilter('all');
  };

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
              <CourseBadge courseType={competition.course_type} variant="dark" />
              <span className="text-xs font-medium text-slate-300">{course.description}</span>
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
              {competition.source_url && (
                <a
                  href={competition.source_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1.5 text-blue-200 hover:text-white hover:underline"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.5 6H18m0 0v4.5M18 6l-7.5 7.5" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 6h4.5M6 6v12h12v-4.5" />
                  </svg>
                  Fuente oficial
                </a>
              )}
            </div>
          </div>
          
          <div className="bg-white/10 backdrop-blur-sm rounded-xl p-4 text-center min-w-32 border border-white/10 shadow-inner">
            <span className="block text-3xl font-black text-white leading-none">{totalUniquePruebas}</span>
            <span className="text-xs font-medium text-slate-300 uppercase tracking-widest mt-1 block">Pruebas Totales</span>
          </div>
        </div>
      </div>

      {statsQuery.data && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
          {[
            ['Participantes', statsQuery.data.participants_count],
            ['Mujeres', statsQuery.data.women_count],
            ['Hombres', statsQuery.data.men_count],
            ['Clubes', statsQuery.data.clubs_count],
            ['Pruebas', statsQuery.data.events_count],
            ['Válidos', statsQuery.data.valid_results_count],
            ['DQ', statsQuery.data.dsq_count],
            ['Entradas', statsQuery.data.entries_count],
          ].map(([label, value]) => (
            <div key={label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-xs font-bold uppercase tracking-widest text-slate-500">{label}</p>
              <p className="mt-1 text-2xl font-black text-slate-900">{value}</p>
            </div>
          ))}
        </div>
      )}

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
        {hasActiveFilters && (
          <button
            type="button"
            onClick={clearFilters}
            className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50 hover:text-slate-900 md:w-auto"
          >
            Limpiar filtros
          </button>
        )}
      </div>

      {/* Resultados por Evento */}
      <div className="space-y-4">
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight mb-6">Resultados</h2>
        
        {groupedEvents.length === 0 ? (
          <EmptyState 
            title="No se encontraron resultados" 
            description={isSearching ? "Intenta con otros términos de búsqueda." : "No hay resultados cargados para esta competencia."} 
          />
        ) : (
          <div className="flex flex-col gap-4">
            {groupedEvents.map((group) => (
              <PruebaCard 
                key={group.pruebaKey} 
                group={group} 
                isSearching={isSearching} 
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
