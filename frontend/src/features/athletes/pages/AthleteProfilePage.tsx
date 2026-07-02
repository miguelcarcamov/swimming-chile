import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { athleteService } from '../api/athleteService';
import { LoadingState } from '../../../components/ui/LoadingState';
import { ErrorState } from '../../../components/ui/ErrorState';
import { EmptyState } from '../../../components/ui/EmptyState';
import { CourseBadge } from '../../../components/ui/CourseBadge';
import { getCourseMeta } from '../../../lib/courseMeta';
import type { CourseType } from '../../../lib/schemas/canon';
import { FavoriteButton } from '../../account/components/FavoriteButton';
import { AthleteClaimForm } from '../../account/components/AthleteClaimForm';
import { ProfileContributionForm } from '../../account/components/ProfileContributionForm';

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
  female: 'Dama',
  male: 'Varón',
};

type BestTimesCourseFilter = 'scm' | 'lcm' | 'all' ;

const courseFilterLabels: Record<BestTimesCourseFilter, string> = {
  scm: 'Piscina corta',
  lcm: 'Piscina larga',
  all: 'Ambas',
};

const formatMonthYear = (date?: string | null) => {
  if (!date) return null;

  const dateString = date.includes('T') ? date : `${date}T12:00:00`;
  const dateObj = new Date(dateString);
  if (Number.isNaN(dateObj.getTime())) return null;

  return dateObj.toLocaleDateString('es-CL', { month: 'short', year: 'numeric' });
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

type TrendPoint = {
  id: string | number;
  competition_name: string;
  competition_date?: string | null;
  course_type?: CourseType | null;
  result_time_text?: string | null;
  result_time_ms: number;
};

const PerformanceTrendChart: React.FC<{ points: TrendPoint[] }> = ({ points }) => {
  if (points.length === 0) return null;

  const chartWidth = 720;
  const chartHeight = 260;
  const padding = { top: 24, right: 24, bottom: 72, left: 64 };
  const plotWidth = chartWidth - padding.left - padding.right;
  const plotHeight = chartHeight - padding.top - padding.bottom;
  const times = points.map(point => point.result_time_ms);
  const minTime = Math.min(...times);
  const maxTime = Math.max(...times);
  const range = maxTime - minTime || 1000;
  const yMin = minTime - range * 0.08;
  const yMax = maxTime + range * 0.08;
  const xForIndex = (index: number) => padding.left + (points.length === 1 ? plotWidth / 2 : (index / (points.length - 1)) * plotWidth);
  const yForTime = (timeMs: number) => padding.top + ((yMax - timeMs) / (yMax - yMin)) * plotHeight;
  const yTicks = [yMin, (yMin + yMax) / 2, yMax];

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="min-w-[680px]">
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={padding.top + plotHeight} stroke="#cbd5e1" />
        <line x1={padding.left} y1={padding.top + plotHeight} x2={padding.left + plotWidth} y2={padding.top + plotHeight} stroke="#cbd5e1" />
        {yTicks.map(tick => (
          <g key={tick}>
            <line x1={padding.left - 4} y1={yForTime(tick)} x2={padding.left + plotWidth} y2={yForTime(tick)} stroke="#e2e8f0" />
            <text x={padding.left - 10} y={yForTime(tick) + 4} textAnchor="end" className="fill-slate-500 text-[11px]">
              {(tick / 1000).toFixed(2)}s
            </text>
          </g>
        ))}
        {points.slice(1).map((point, index) => {
          const previous = points[index];
          const improved = point.result_time_ms < previous.result_time_ms;

          return (
            <line
              key={`${previous.id}-${point.id}`}
              x1={xForIndex(index)}
              y1={yForTime(previous.result_time_ms)}
              x2={xForIndex(index + 1)}
              y2={yForTime(point.result_time_ms)}
              stroke={improved ? '#059669' : '#dc2626'}
              strokeWidth="3"
              strokeDasharray="6 4"
              strokeLinecap="round"
            />
          );
        })}
        {points.map((point, index) => {
          const x = xForIndex(index);
          const y = yForTime(point.result_time_ms);
          const date = formatMonthYear(point.competition_date);
          const course = getCourseMeta(point.course_type);

          return (
            <g key={point.id}>
              <circle cx={x} cy={y} r="5" className={point.course_type === 'lcm' ? 'fill-violet-600 stroke-white' : 'fill-blue-600 stroke-white'} strokeWidth="2">
                <title>{`${point.competition_name}: ${point.result_time_text || `${(point.result_time_ms / 1000).toFixed(2)}s`} · ${course.description}`}</title>
              </circle>
              <text x={x} y={y - 10} textAnchor="middle" className="fill-slate-700 text-[11px] font-semibold">
                {point.result_time_text}
              </text>
              <text x={x} y={padding.top + plotHeight + 20} textAnchor="middle" className="fill-slate-500 text-[10px]">
                {date || `Registro ${index + 1}`}
              </text>
              <text x={x} y={padding.top + plotHeight + 36} textAnchor="middle" className="fill-slate-400 text-[10px]">
                {point.competition_name.length > 16 ? `${point.competition_name.slice(0, 16)}…` : point.competition_name}
              </text>
            </g>
          );
        })}
        <g transform={`translate(${padding.left}, ${chartHeight - 10})`}>
          <circle cx="0" cy="0" r="4" className="fill-blue-600" />
          <text x="10" y="4" className="fill-slate-500 text-[11px]">Piscina corta</text>
          <circle cx="110" cy="0" r="4" className="fill-violet-600" />
          <text x="120" y="4" className="fill-slate-500 text-[11px]">Piscina larga</text>
        </g>
      </svg>
    </div>
  );
};

export const AthleteProfilePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [courseFilter, setCourseFilter] = React.useState<BestTimesCourseFilter>('all');
  const [trendSelection, setTrendSelection] = React.useState('');

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

  const availablePoolFilters = React.useMemo(
    () => new Set(pbs.map(res => res.course_type).filter((course): course is 'scm' | 'lcm' => course === 'scm' || course === 'lcm')),
    [pbs],
  );

  const filteredPbs = React.useMemo(
    () => courseFilter === 'all' ? pbs : pbs.filter(res => res.course_type === courseFilter),
    [pbs, courseFilter],
  );

  const trendOptions = React.useMemo(() => {
    if (!athlete?.recent_results) return [];

    const options = new Map<string, { key: string; label: string }>();
    athlete.recent_results.forEach(result => {
      if (result.status !== 'valid' || !result.result_time_ms || !result.distance_m || !result.stroke) return;
      const key = `${result.distance_m}-${result.stroke}`;
      options.set(key, {
        key,
        label: `${result.distance_m}m ${strokeTranslations[result.stroke]}`,
      });
    });

    return Array.from(options.values()).sort((a, b) => a.label.localeCompare(b.label));
  }, [athlete]);

  const selectedTrendKey = trendOptions.some(option => option.key === trendSelection)
    ? trendSelection
    : trendOptions[0]?.key || '';

  const trendPoints = React.useMemo(() => {
    if (!athlete?.recent_results || !selectedTrendKey) return [];

    const [distance, stroke] = selectedTrendKey.split('-');
    return athlete.recent_results
      .map((result, index) => ({ result, index }))
      .filter(({ result }) => (
        result.status === 'valid' &&
        result.result_time_ms &&
        result.distance_m?.toString() === distance &&
        result.stroke === stroke
      ))
      .sort((a, b) => {
        const leftDate = a.result.competition_date ? new Date(`${a.result.competition_date}T12:00:00`).getTime() : 0;
        const rightDate = b.result.competition_date ? new Date(`${b.result.competition_date}T12:00:00`).getTime() : 0;
        return rightDate - leftDate || a.index - b.index;
      })
      .slice(0, 5)
      .reverse()
      .map(({ result }) => ({
        id: result.id,
        competition_name: result.competition_name,
        competition_date: result.competition_date,
        course_type: result.course_type,
        result_time_text: result.result_time_text,
        result_time_ms: result.result_time_ms!,
      }));
  }, [athlete, selectedTrendKey]);

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
          <div className="min-w-0 flex-1">
            <h1 className="text-3xl font-bold text-slate-900 tracking-tight">{athlete.full_name}</h1>
            <div className="mt-2 flex flex-wrap gap-3">
              <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-50 text-blue-700 border border-blue-100 capitalize">
                {athlete.gender ? genderTranslations[athlete.gender] : 'Sin género'}
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
          <div className="md:ml-auto">
            <FavoriteButton targetType="athlete" targetId={athlete.id} />
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <AthleteClaimForm
          athleteId={athlete.id}
          currentClubName={athlete.current_club_name || athlete.club_name}
        />
        <ProfileContributionForm targetType="athlete" targetId={athlete.id} />
      </div>

      {/* Mejores Tiempos */}
      {pbs.length > 0 && (
        <div>
          <div className="mb-4 flex flex-col gap-3 px-1 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-xl font-bold text-slate-900">Mejores Tiempos</h2>
            <div className="flex flex-wrap gap-2">
              {(['scm', 'lcm', 'all'] as const).map(course => {
                const meta = course === 'all' ? null : getCourseMeta(course as CourseType);
                const isActive = courseFilter === course;
                const isDisabled = course !== 'all' && !availablePoolFilters.has(course);

                return (
                  <button
                    key={course}
                    type="button"
                    disabled={isDisabled}
                    onClick={() => setCourseFilter(course)}
                    className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-bold uppercase tracking-wider transition-colors ${
                      isActive ? (meta?.light || 'border-slate-300 bg-slate-100 text-slate-700') : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50'
                    } ${isDisabled ? 'cursor-not-allowed opacity-40' : ''}`}
                  >
                    {courseFilterLabels[course]}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredPbs.map(res => {
              const achievedAt = formatMonthYear(res.competition_date);

              return (
              <div key={res.id} className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 flex items-center justify-between">
                <div>
                  <div className="font-bold text-slate-900">{res.distance_m}m {res.stroke ? strokeTranslations[res.stroke] : 'Estilo no informado'}</div>
                  <div className="text-xs text-slate-500 uppercase flex items-center gap-2 mt-0.5 tracking-wider">
                    <CourseBadge courseType={res.course_type} variant="compact" />
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
                  <div className="text-xs text-slate-500 truncate max-w-[150px]" title={res.competition_name}>
                    {achievedAt && <span className="ml-1 text-slate-400">({achievedAt}) </span>}
                    {res.competition_name}
                  </div>
                </div>
              </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Evolución de Tiempos */}
      {trendOptions.length > 0 && (
        <div>
          <div className="mb-4 flex flex-col gap-3 px-1 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-xl font-bold text-slate-900">Evolución de Tiempos</h2>
              <p className="text-sm text-slate-500">
                Últimos 5 registros ordenados de más antiguo a más reciente.
              </p>
            </div>
            <select
              value={selectedTrendKey}
              onChange={(event) => setTrendSelection(event.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:ring-2 focus:ring-blue-500 sm:w-72"
            >
              {trendOptions.map(option => (
                <option key={option.key} value={option.key}>{option.label}</option>
              ))}
            </select>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            {trendPoints.length > 0 ? (
              <PerformanceTrendChart points={trendPoints} />
            ) : (
              <EmptyState title="Sin registros suficientes" description="No hay tiempos válidos para esta selección." />
            )}
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
            {Object.entries(groupedRecent).map(([compName, results]) => {
              const competitionMonthYear = formatMonthYear(results[0]?.competition_date);

              return (
              <div key={compName} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                <div className="bg-slate-50 border-b border-slate-200 px-4 py-3">
                  <h3 className="font-bold text-slate-800">
                    {compName}
                    {competitionMonthYear && <span className="ml-2 text-sm font-medium text-slate-500">({competitionMonthYear})</span>}
                  </h3>
                </div>
                <div className="divide-y divide-slate-100">
                  {results.map(res => (
                    <div key={res.id} className="px-4 py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-slate-50/50 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-blue-50 flex items-center justify-center text-blue-700 font-bold text-sm shrink-0">
                          {res.rank_position ? `${res.rank_position}°` : '-'}
                        </div>
                        <div>
                          <div className="font-semibold text-slate-900">{res.distance_m}m {res.stroke ? strokeTranslations[res.stroke] : 'Estilo no informado'}</div>
                          <div className="text-xs text-slate-500 uppercase flex items-center gap-2">
                            <CourseBadge courseType={res.course_type} variant="compact" />
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
                          <TimeComparison seedMs={res.seed_time_ms} resultMs={res.result_time_ms} />
                          {res.status !== 'valid' && (
                            <span className="text-xs font-bold text-red-600 bg-red-50 px-1.5 py-0.5 rounded">{res.status}</span>
                          )}
                        </div>
                        {res.seed_time_text && (
                          <div className="text-xs text-slate-500 mt-1">
                            Seed {res.seed_time_text}
                          </div>
                        )}
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
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
