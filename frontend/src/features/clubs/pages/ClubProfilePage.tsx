import React from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { clubService } from '../api/clubService';
import { athleteService } from '../../athletes/api/athleteService';
import { LoadingState } from '../../../components/ui/LoadingState';
import { ErrorState } from '../../../components/ui/ErrorState';
import { EmptyState } from '../../../components/ui/EmptyState';
import { FavoriteButton } from '../../account/components/FavoriteButton';
import { ProfileContributionForm } from '../../account/components/ProfileContributionForm';

const formatCompetitionMonthYear = (date?: string | null) => {
  if (!date) return null;

  const dateString = date.includes('T') ? date : `${date}T12:00:00`;
  const dateObj = new Date(dateString);
  if (Number.isNaN(dateObj.getTime())) return null;

  return dateObj.toLocaleDateString('es-CL', { month: 'short', year: 'numeric' });
};

type AttendanceTrendPoint = {
  competition_id: string | number;
  competition_name: string;
  competition_date?: string | null;
  attended_count: number;
  attendance_percentage: number;
};

const AttendanceTrendChart: React.FC<{ points: AttendanceTrendPoint[] }> = ({ points }) => {
  if (points.length === 0) return null;

  const chartHeight = 240;
  const minChartWidth = 720;
  const pointSpacing = 112;
  const padding = { top: 24, right: 24, bottom: 68, left: 56 };
  const chartWidth = Math.max(minChartWidth, padding.left + padding.right + Math.max(points.length - 1, 1) * pointSpacing);
  const plotWidth = chartWidth - padding.left - padding.right;
  const plotHeight = chartHeight - padding.top - padding.bottom;
  const xForIndex = (index: number) => padding.left + (points.length === 1 ? plotWidth / 2 : (index / (points.length - 1)) * plotWidth);
  const yForPercent = (percent: number) => padding.top + ((100 - percent) / 100) * plotHeight;
  const yTicks = [0, 50, 100];

  return (
    <div className="overflow-x-auto">
      <svg
        viewBox={`0 0 ${chartWidth} ${chartHeight}`}
        width={chartWidth}
        height={chartHeight}
        className="min-w-full max-w-none"
      >
        <line x1={padding.left} y1={padding.top} x2={padding.left} y2={padding.top + plotHeight} stroke="#cbd5e1" />
        <line x1={padding.left} y1={padding.top + plotHeight} x2={padding.left + plotWidth} y2={padding.top + plotHeight} stroke="#cbd5e1" />
        {yTicks.map(tick => (
          <g key={tick}>
            <line x1={padding.left - 4} y1={yForPercent(tick)} x2={padding.left + plotWidth} y2={yForPercent(tick)} stroke="#e2e8f0" />
            <text x={padding.left - 10} y={yForPercent(tick) + 4} textAnchor="end" className="fill-slate-500 text-[11px]">
              {tick}%
            </text>
          </g>
        ))}
        {points.slice(1).map((point, index) => {
          const previous = points[index];
          const improved = point.attendance_percentage >= previous.attendance_percentage;

          return (
            <line
              key={`${previous.competition_id}-${point.competition_id}`}
              x1={xForIndex(index)}
              y1={yForPercent(previous.attendance_percentage)}
              x2={xForIndex(index + 1)}
              y2={yForPercent(point.attendance_percentage)}
              stroke={improved ? '#059669' : '#dc2626'}
              strokeWidth="3"
              strokeDasharray="6 4"
              strokeLinecap="round"
            />
          );
        })}
        {points.map((point, index) => {
          const x = xForIndex(index);
          const y = yForPercent(point.attendance_percentage);
          const date = formatCompetitionMonthYear(point.competition_date);

          return (
            <g key={point.competition_id}>
              <circle cx={x} cy={y} r="5" className="fill-blue-600 stroke-white" strokeWidth="2">
                <title>{`${point.competition_name}: ${point.attended_count} asistentes (${point.attendance_percentage}%)`}</title>
              </circle>
              <text x={x} y={y - 10} textAnchor="middle" className="fill-slate-700 text-[11px] font-semibold">
                {point.attendance_percentage}% ({point.attended_count})
              </text>
              <text x={x} y={padding.top + plotHeight + 20} textAnchor="middle" className="fill-slate-500 text-[10px]">
                {date || `Competencia ${index + 1}`}
              </text>
              <text x={x} y={padding.top + plotHeight + 36} textAnchor="middle" className="fill-slate-400 text-[10px]">
                {point.competition_name.length > 16 ? `${point.competition_name.slice(0, 16)}…` : point.competition_name}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
};

export const ClubProfilePage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // Estados para filtros de atletas
  const [searchTerm, setSearchTerm] = React.useState('');
  const [debouncedQuery, setDebouncedQuery] = React.useState('');
  const [gender, setGender] = React.useState('all');
  const [page, setPage] = React.useState(1);
  const [attendanceYear, setAttendanceYear] = React.useState('all');
  const hasActiveFilters = searchTerm.trim() !== '' || gender !== 'all';

  const clearFilters = () => {
    setSearchTerm('');
    setDebouncedQuery('');
    setGender('all');
    setPage(1);
  };

  React.useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedQuery(searchTerm);
      setPage(1);
    }, 400);
    return () => clearTimeout(handler);
  }, [searchTerm]);

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

  const attendanceMatrix = club.attendance_matrix;
  const attendanceYears = attendanceMatrix
    ? Array.from(new Set(
        attendanceMatrix.competitions
          .map(competition => competition.date ? new Date(`${competition.date}T12:00:00`).getFullYear() : null)
          .filter((year): year is number => Boolean(year))
      )).sort((a, b) => b - a)
    : [];
  const visibleAttendanceCompetitions = attendanceMatrix
    ? attendanceMatrix.competitions.filter(competition => (
        attendanceYear === 'all' ||
        (competition.date && new Date(`${competition.date}T12:00:00`).getFullYear().toString() === attendanceYear)
      ))
    : [];
  const currentAthleteTotal = club.total_athletes || attendanceMatrix?.athletes.length || 0;
  const attendanceTrendPoints = attendanceMatrix
    ? visibleAttendanceCompetitions
        .map(competition => {
          const attendedCount = attendanceMatrix.athletes.reduce((count, athlete) => {
            const attendance = athlete.competitions.find(entry => String(entry.competition_id) === String(competition.id));
            return attendance?.status === 'attended' ? count + 1 : count;
          }, 0);

          return {
            competition_id: competition.id,
            competition_name: competition.name,
            competition_date: competition.date,
            attended_count: attendedCount,
            attendance_percentage: currentAthleteTotal > 0 ? Math.round((attendedCount / currentAthleteTotal) * 100) : 0,
          };
        })
        .sort((a, b) => {
          const leftDate = a.competition_date ? new Date(`${a.competition_date}T12:00:00`).getTime() : 0;
          const rightDate = b.competition_date ? new Date(`${b.competition_date}T12:00:00`).getTime() : 0;
          return leftDate - rightDate || a.competition_name.localeCompare(b.competition_name);
        })
    : [];

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
          <div className="min-w-0 flex-1">
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
          <div className="md:ml-auto">
            <FavoriteButton targetType="club" targetId={club.id} />
          </div>
        </div>
      </div>

      <ProfileContributionForm targetType="club" targetId={club.id} />

      {/* Asistencia por Competencia */}
      {attendanceMatrix && attendanceMatrix.competitions.length > 0 && attendanceMatrix.athletes.length > 0 && (
        <div>
          <div className="mb-4 flex flex-col gap-3 px-1 sm:flex-row sm:items-center sm:justify-between">
            <h2 className="text-xl font-bold text-slate-900">Asistencia a Competencias</h2>
            <select
              value={attendanceYear}
              onChange={(event) => setAttendanceYear(event.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:ring-2 focus:ring-blue-500 sm:w-40"
            >
              <option value="all">Todos los años</option>
              {attendanceYears.map(year => (
                <option key={year} value={year}>{year}</option>
              ))}
            </select>
          </div>
          <div className="bg-white rounded-xl shadow-sm border border-slate-200">
            <div className="px-4 py-3 border-b border-slate-200 bg-slate-50">
              <p className="text-sm text-slate-600">
                Atletas inscritos representando a {club.name}. ✓ indica que compitió; × indica inscripción sin participación registrada.
              </p>
            </div>
            <div className="max-h-[70vh] overflow-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-white border-b border-slate-200">
                  <tr>
                    <th className="sticky left-0 top-0 z-40 bg-white px-4 py-3 text-left font-semibold text-slate-700 min-w-56 shadow-sm">
                      Atleta
                    </th>
                    {visibleAttendanceCompetitions.map(competition => (
                      <th key={competition.id} className="sticky top-0 z-30 bg-white px-3 py-3 text-center font-semibold text-slate-700 min-w-32 shadow-sm">
                        <Link
                          to={`/competitions/${competition.id}`}
                          className="block text-blue-700 hover:text-blue-900 hover:underline"
                          title={competition.name}
                        >
                          <span className="line-clamp-2">{competition.name}</span>
                        </Link>
                        {formatCompetitionMonthYear(competition.date) && (
                          <span className="mt-1 block text-xs font-medium text-slate-400">
                            {formatCompetitionMonthYear(competition.date)}
                          </span>
                        )}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {attendanceMatrix.athletes.map(athlete => {
                    const attendanceByCompetition = new Map(
                      athlete.competitions.map(entry => [String(entry.competition_id), entry])
                    );
                    const hasAttendanceInVisibleYear = visibleAttendanceCompetitions.some(competition => (
                      attendanceByCompetition.get(String(competition.id))?.status === 'attended'
                    ));
                    const highlightNoAttendance = attendanceYear !== 'all' && !hasAttendanceInVisibleYear;

                    return (
                      <tr key={athlete.athlete_id} className={highlightNoAttendance ? 'bg-red-50/60 hover:bg-red-50' : 'hover:bg-slate-50/60'}>
                        <th className={`sticky left-0 z-10 px-4 py-3 text-left font-semibold min-w-56 ${highlightNoAttendance ? 'bg-red-50 text-red-800' : 'bg-white text-slate-900'}`}>
                          <Link to={`/athletes/${athlete.athlete_id}`} className="hover:text-blue-700 hover:underline">
                            {athlete.athlete_name}
                          </Link>
                          {highlightNoAttendance && (
                            <span className="ml-2 text-xs font-medium text-red-600">
                              Sin participación
                            </span>
                          )}
                        </th>
                        {visibleAttendanceCompetitions.map(competition => {
                          const attendance = attendanceByCompetition.get(String(competition.id));

                          return (
                            <td key={`${athlete.athlete_id}-${competition.id}`} className="px-3 py-3 text-center">
                              {attendance?.status === 'attended' ? (
                                <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-emerald-50 text-sm font-bold text-emerald-700 border border-emerald-100" title="Compitió">
                                  ✓
                                </span>
                              ) : attendance?.status === 'no_show' ? (
                                <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-red-50 text-sm font-bold text-red-700 border border-red-100" title="Inscrito, no compitió">
                                  ×
                                </span>
                              ) : (
                                <span className="text-slate-300">—</span>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot className="border-t-2 border-slate-200 bg-slate-50">
                  <tr>
                    <th className="sticky left-0 z-10 bg-slate-50 px-4 py-3 text-left font-bold text-slate-800 min-w-56">
                      Asistencia
                      <span className="block text-xs font-medium text-slate-500">
                        sobre {currentAthleteTotal} atletas vigentes
                      </span>
                    </th>
                    {visibleAttendanceCompetitions.map(competition => {
                      const attendedCount = attendanceMatrix.athletes.reduce((count, athlete) => {
                        const attendance = athlete.competitions.find(entry => String(entry.competition_id) === String(competition.id));
                        return attendance?.status === 'attended' ? count + 1 : count;
                      }, 0);
                      const attendancePercentage = currentAthleteTotal > 0
                        ? Math.round((attendedCount / currentAthleteTotal) * 100)
                        : 0;

                      return (
                        <td key={`summary-${competition.id}`} className="px-3 py-3 text-center">
                          <span className="block font-bold text-slate-900">{attendedCount}</span>
                          <span className="text-xs font-medium text-slate-500">{attendancePercentage}%</span>
                        </td>
                      );
                    })}
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>

          {attendanceTrendPoints.length > 0 && (
            <div className="mt-6">
              <div className="mb-4 px-1">
                <h3 className="text-lg font-bold text-slate-900">Evolución de Asistencia</h3>
                <p className="text-sm text-slate-500">
                  Porcentaje de atletas vigentes que participaron por competencia.
                </p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <AttendanceTrendChart points={attendanceTrendPoints} />
              </div>
            </div>
          )}
        </div>
      )}

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
            onChange={(e) => {
              setGender(e.target.value);
              setPage(1);
            }}
            className="px-4 py-2 border border-slate-300 rounded-lg shadow-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white text-sm text-slate-700 cursor-pointer"
          >
            <option value="all">Todos los géneros</option>
            <option value="female">Damas</option>
            <option value="male">Varones</option>
          </select>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="whitespace-nowrap rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-600 shadow-sm transition-colors hover:bg-slate-50 hover:text-slate-900"
            >
              Limpiar
            </button>
          )}
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
