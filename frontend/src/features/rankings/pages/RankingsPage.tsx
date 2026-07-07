import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { rankingService } from '../api/rankingService';
import { LoadingState } from '../../../components/ui/LoadingState';
import { ErrorState } from '../../../components/ui/ErrorState';
import { EmptyState } from '../../../components/ui/EmptyState';

const strokeLabels: Record<string, string> = {
  freestyle: 'Libre',
  backstroke: 'Espalda',
  breaststroke: 'Pecho',
  butterfly: 'Mariposa',
  individual_medley: 'Combinado',
};

const genderLabels: Record<string, string> = {
  women: 'Damas',
  men: 'Varones',
  mixed: 'Mixto',
};

const courseLabels: Record<string, string> = {
  scm: 'Piscina corta',
  lcm: 'Piscina larga',
  unknown: 'Sin dato de piscina',
};

type AnalyticsView = 'swimmers' | 'clubs';

export const RankingsPage: React.FC = () => {
  const [activeView, setActiveView] = React.useState<AnalyticsView>('swimmers');
  const [distance, setDistance] = React.useState('50');
  const [stroke, setStroke] = React.useState('freestyle');
  const [gender, setGender] = React.useState('men');
  const [ageGroup, setAgeGroup] = React.useState('all');
  const [courseType, setCourseType] = React.useState('all');
  const [year, setYear] = React.useState('all');
  const [page, setPage] = React.useState(1);
  const [athleteSearchInput, setAthleteSearchInput] = React.useState('');
  const [athleteSearch, setAthleteSearch] = React.useState('');

  const filtersQuery = useQuery({
    queryKey: ['ranking-filter-options'],
    queryFn: () => rankingService.getFilterOptions(),
  });

  const validEventOptions = filtersQuery.data?.event_options || [];
  const selectedEventIsValid = validEventOptions.length === 0 || validEventOptions.some(
    (option) => option.distance_m === Number(distance) && option.stroke === stroke
  );
  const normalizedDistance = selectedEventIsValid ? distance : String(validEventOptions[0]?.distance_m || distance);
  const normalizedStroke = selectedEventIsValid ? stroke : (validEventOptions[0]?.stroke || stroke);
  const strokeOptions = validEventOptions.length
    ? Array.from(new Set(validEventOptions.map((option) => option.stroke)))
    : (filtersQuery.data?.strokes.length ? filtersQuery.data.strokes : Object.keys(strokeLabels));
  const distanceOptions = validEventOptions.length
    ? Array.from(new Set(
        validEventOptions
          .filter((option) => option.stroke === normalizedStroke)
          .map((option) => option.distance_m)
      ))
    : (filtersQuery.data?.distances.length ? filtersQuery.data.distances : [50, 100, 200, 400]);

  const rankingsQuery = useQuery({
    queryKey: ['rankings', normalizedDistance, normalizedStroke, gender, ageGroup, courseType, year, athleteSearch, page],
    queryFn: () => rankingService.getRankings({
      distance_m: normalizedDistance,
      stroke: normalizedStroke,
      gender,
      age_group: ageGroup,
      course_type: courseType,
      year,
      athlete_search: athleteSearch,
      page,
    }),
    enabled: activeView === 'swimmers',
  });

  const clubParticipationQuery = useQuery({
    queryKey: ['club-participation'],
    queryFn: () => rankingService.getClubParticipation(1),
    enabled: activeView === 'clubs',
  });

  const resetPage = (setter: (value: string) => void) => (value: string) => {
    setter(value);
    setPage(1);
  };

  const updateDistance = (nextDistance: string) => {
    setDistance(nextDistance);
    setPage(1);
  };

  const updateStroke = (nextStroke: string) => {
    const compatibleDistances = validEventOptions
      .filter((option) => option.stroke === nextStroke)
      .map((option) => option.distance_m);
    setStroke(nextStroke);
    if (compatibleDistances.length > 0 && !compatibleDistances.includes(Number(distance))) {
      setDistance(String(compatibleDistances[0]));
    }
    setPage(1);
  };

  const submitAthleteSearch = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setAthleteSearch(athleteSearchInput.trim());
    setPage(1);
  };

  const clearAthleteSearch = () => {
    setAthleteSearchInput('');
    setAthleteSearch('');
    setPage(1);
  };

  const title = `${normalizedDistance}m ${strokeLabels[normalizedStroke] || normalizedStroke} ${genderLabels[gender] || gender}`;
  const subtitle = [
    ageGroup !== 'all' ? `Categoría ${ageGroup}` : 'Todas las categorías',
    courseType !== 'all' ? courseLabels[courseType] || courseType.toUpperCase() : 'Todas las piscinas',
    year !== 'all' ? year : 'Últimos 12 meses',
  ].join(' • ');

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div>
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Rankings y estadísticas</h1>
        <p className="text-slate-500 mt-1">Elige si quieres ver rankings de nadadores o estadísticas de participación.</p>
      </div>

      <div className="grid min-w-0 gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
        <aside className="min-w-0 lg:sticky lg:top-24 lg:self-start">
          <nav className="flex gap-2 overflow-x-auto rounded-xl border border-slate-200 bg-white p-2 shadow-sm lg:grid lg:grid-cols-1 lg:overflow-visible">
            <button
              type="button"
              onClick={() => setActiveView('swimmers')}
              className={`min-w-[180px] rounded-lg px-4 py-3 text-left text-sm font-semibold transition-colors lg:min-w-0 ${
                activeView === 'swimmers'
                  ? 'bg-blue-50 text-blue-700 ring-1 ring-blue-700/10'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              Rankings de nadadores
            </button>
            <button
              type="button"
              onClick={() => setActiveView('clubs')}
              className={`min-w-[180px] rounded-lg px-4 py-3 text-left text-sm font-semibold transition-colors lg:min-w-0 ${
                activeView === 'clubs'
                  ? 'bg-blue-50 text-blue-700 ring-1 ring-blue-700/10'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              Estadísticas de clubes
            </button>
          </nav>
        </aside>

        <div className="min-w-0 space-y-6">
          {activeView === 'swimmers' && (
            <>
              <section className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                  <select value={normalizedStroke} onChange={(event) => updateStroke(event.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
                    {strokeOptions.map((value) => (
                      <option key={value} value={value}>{strokeLabels[value] || value}</option>
                    ))}
                  </select>
                  <select value={normalizedDistance} onChange={(event) => updateDistance(event.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
                    {distanceOptions.map((value) => (
                      <option key={value} value={value}>{value}m</option>
                    ))}
                  </select>
                  <select value={gender} onChange={(event) => resetPage(setGender)(event.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
                    <option value="women">Damas</option>
                    <option value="men">Varones</option>
                    <option value="mixed">Mixto</option>
                  </select>
                  <select value={ageGroup} onChange={(event) => resetPage(setAgeGroup)(event.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
                    <option value="all">Todas las categorías</option>
                    {filtersQuery.data?.age_groups.map((value) => (
                      <option key={value} value={value}>{value}</option>
                    ))}
                  </select>
                  <select value={courseType} onChange={(event) => resetPage(setCourseType)(event.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
                    <option value="all">Todas las piscinas</option>
                    <option value="scm">Piscina corta</option>
                    <option value="lcm">Piscina larga</option>
                    <option value="unknown">Sin dato</option>
                  </select>
                  <select value={year} onChange={(event) => resetPage(setYear)(event.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm">
                    <option value="all">Últimos 12 meses</option>
                    {filtersQuery.data?.years.map((value) => (
                      <option key={value} value={value}>{value}</option>
                    ))}
                  </select>
                </div>

                <form onSubmit={submitAthleteSearch} className="mt-4 flex flex-col gap-2 sm:flex-row">
                  <input
                    type="search"
                    value={athleteSearchInput}
                    onChange={(event) => setAthleteSearchInput(event.target.value)}
                    placeholder="Buscar atleta en este ranking"
                    className="min-w-0 flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                  />
                  <div className="flex gap-2">
                    <button type="submit" className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700">
                      Buscar
                    </button>
                    {athleteSearch && (
                      <button type="button" onClick={clearAthleteSearch} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
                        Limpiar
                      </button>
                    )}
                  </div>
                </form>

                {athleteSearch && (
                  <p className="mt-3 text-sm text-slate-500">
                    Mostrando coincidencias para <span className="font-semibold text-slate-700">{athleteSearch}</span> dentro del ranking filtrado.
                  </p>
                )}
              </section>

              <section className="space-y-4">
                <div className="bg-slate-900 rounded-xl p-6 text-white shadow-lg shadow-slate-900/20">
                  <h2 className="text-xl font-bold">Top marcas - {title}</h2>
                  <p className="text-slate-300 text-sm mt-1">{subtitle}</p>
                </div>

                {rankingsQuery.isLoading && <LoadingState />}
                {rankingsQuery.isError && <ErrorState onRetry={() => rankingsQuery.refetch()} />}

                {!rankingsQuery.isLoading && !rankingsQuery.isError && rankingsQuery.data && (
                  rankingsQuery.data.data.length === 0 ? (
                    <EmptyState title="No hay marcas para estos filtros" description="Prueba con otra categoría, prueba o piscina." />
                  ) : (
                    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                      <div className="divide-y divide-slate-100 md:hidden">
                        {rankingsQuery.data.data.map((entry) => (
                          <article key={`mobile-${entry.rank}-${entry.athlete_id}-${entry.time_ms}`} className="p-4">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="text-xs font-bold uppercase tracking-widest text-blue-600">#{entry.rank}</p>
                                <Link to={`/athletes/${entry.athlete_id}`} className="mt-1 block truncate font-semibold text-slate-900 hover:text-blue-600 hover:underline">
                                  {entry.athlete_name}
                                </Link>
                                <p className="mt-1 truncate text-sm text-slate-500">{entry.club_name || 'Sin club'}</p>
                              </div>
                              <span className="shrink-0 font-mono text-lg font-bold text-blue-700">{entry.time_text}</span>
                            </div>
                            <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-slate-500">
                              <div>
                                <p className="font-semibold text-slate-700">{entry.age_group}</p>
                                {entry.current_age && <p>{entry.current_age} años</p>}
                              </div>
                              <div className="text-right">
                                <Link to={`/competitions/${entry.competition_id}`} className="block truncate hover:text-blue-600 hover:underline">
                                  {entry.competition_name}
                                </Link>
                                <p className="text-slate-400">
                                  {entry.date ? new Date(`${entry.date}T12:00:00`).getFullYear() : 's/f'}
                                  {' '}• categoría {entry.event_age_group}
                                </p>
                              </div>
                            </div>
                          </article>
                        ))}
                      </div>

                      <div className="hidden overflow-x-auto md:block">
                        <table className="w-full text-sm text-left">
                          <thead className="bg-slate-50 text-slate-600 font-medium border-b border-slate-200">
                            <tr>
                              <th className="px-6 py-4 w-16 text-center">Pos</th>
                              <th className="px-6 py-4">Atleta</th>
                              <th className="px-6 py-4">Club</th>
                              <th className="px-6 py-4">Tiempo</th>
                              <th className="px-6 py-4 text-center">Categoría actual</th>
                              <th className="px-6 py-4">Competencia</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {rankingsQuery.data.data.map((entry) => (
                              <tr key={`${entry.rank}-${entry.athlete_id}-${entry.time_ms}`} className="hover:bg-slate-50 transition-colors">
                                <td className="px-6 py-4 text-center">
                                  <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full font-bold ${
                                    entry.rank === 1 ? 'bg-amber-100 text-amber-700 ring-1 ring-amber-300' :
                                    entry.rank === 2 ? 'bg-slate-100 text-slate-600 ring-1 ring-slate-300' :
                                    entry.rank === 3 ? 'bg-orange-50 text-orange-700 ring-1 ring-orange-200' :
                                    'text-slate-500'
                                  }`}>
                                    {entry.rank}
                                  </span>
                                </td>
                                <td className="px-6 py-4 font-semibold text-slate-900">
                                  <Link to={`/athletes/${entry.athlete_id}`} className="hover:text-blue-600 hover:underline">
                                    {entry.athlete_name}
                                  </Link>
                                </td>
                                <td className="px-6 py-4 text-slate-600">{entry.club_name || 'Sin club'}</td>
                                <td className="px-6 py-4 ">
                                  <span className="font-mono font-bold text-blue-700 text-base">{entry.time_text}</span>
                                </td>
                                <td className="px-6 py-4 text-slate-600 text-center">
                                  <span className="font-medium text-slate-800">{entry.age_group}</span>
                                  {entry.current_age && (
                                    <span className="block text-xs text-slate-400">{entry.current_age} años</span>
                                  )}
                                </td>
                                <td className="px-6 py-4 text-slate-500 text-xs">
                                  <Link to={`/competitions/${entry.competition_id}`} className="hover:text-blue-600 hover:underline">
                                    {entry.competition_name}
                                  </Link>
                                  <br />
                                  <span className="text-slate-400">
                                    {entry.date ? new Date(`${entry.date}T12:00:00`).getFullYear() : 's/f'}
                                    {' '}• categoría {entry.event_age_group}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <div className="flex flex-col gap-3 border-t border-slate-200 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
                        <p className="text-sm text-slate-500">
                          Página {rankingsQuery.data.meta.page} de {rankingsQuery.data.meta.total_pages}
                        </p>
                        <div className="flex gap-2">
                          <button onClick={() => setPage((currentPage) => Math.max(1, currentPage - 1))} disabled={page === 1} className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium disabled:opacity-50">
                            Anterior
                          </button>
                          <button onClick={() => setPage((currentPage) => Math.min(rankingsQuery.data.meta.total_pages, currentPage + 1))} disabled={page >= rankingsQuery.data.meta.total_pages} className="px-4 py-2 border border-slate-300 rounded-lg text-sm font-medium disabled:opacity-50">
                            Siguiente
                          </button>
                        </div>
                      </div>
                    </div>
                  )
                )}
              </section>
            </>
          )}

          {activeView === 'clubs' && (
            <section className="space-y-4">
              <div>
                <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Clubes con mayor participación</h2>
                <p className="text-slate-500 text-sm">Ordenado por nadadores únicos, competencias disputadas y entradas.</p>
              </div>

              {clubParticipationQuery.isLoading && <LoadingState />}
              {clubParticipationQuery.isError && <ErrorState onRetry={() => clubParticipationQuery.refetch()} />}
              {!clubParticipationQuery.isLoading && !clubParticipationQuery.isError && clubParticipationQuery.data && (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {clubParticipationQuery.data.data.slice(0, 6).map((club) => (
                    <Link key={club.club_id} to={`/clubs/${club.club_id}`} className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm hover:border-blue-300 hover:shadow-md transition-all">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-xs font-bold uppercase tracking-widest text-blue-600">#{club.rank}</p>
                          <h3 className="mt-1 text-lg font-bold text-slate-900">{club.club_name}</h3>
                        </div>
                        <span className="rounded-full bg-blue-50 px-3 py-1 text-sm font-bold text-blue-700">
                          {club.unique_athletes}
                        </span>
                      </div>
                      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                        <div>
                          <p className="text-slate-500">Competencias</p>
                          <p className="font-bold text-slate-900">{club.competitions_count}</p>
                        </div>
                        <div>
                          <p className="text-slate-500">Entradas</p>
                          <p className="font-bold text-slate-900">{club.entries_count}</p>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </section>
          )}
        </div>
      </div>
    </div>
  );
};
