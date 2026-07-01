import React from 'react';
import { clubService } from '../../clubs/api/clubService';
import { relayService } from '../api/relayService';
import type { Club } from '../../../lib/schemas/club';
import type { RelayAnalysisResponse, RelayAthlete, RelayLineup, RelaySlot, RelayType } from '../../../lib/schemas/relay';

const DEFAULT_RELAY_TYPES: RelayType[] = [
  { key: '4x50_medley_mixed', label: '4x50 combinado mixto', distance_m: 50, style: 'medley', gender_rule: 'mixed_2f_2m', slots: [] },
  { key: '4x50_medley_women', label: '4x50 combinado mujeres', distance_m: 50, style: 'medley', gender_rule: 'women', slots: [] },
  { key: '4x50_medley_men', label: '4x50 combinado hombres', distance_m: 50, style: 'medley', gender_rule: 'men', slots: [] },
  { key: '4x50_freestyle_mixed', label: '4x50 libre mixto', distance_m: 50, style: 'freestyle', gender_rule: 'mixed_2f_2m', slots: [] },
  { key: '4x50_freestyle_women', label: '4x50 libre mujeres', distance_m: 50, style: 'freestyle', gender_rule: 'women', slots: [] },
  { key: '4x50_freestyle_men', label: '4x50 libre hombres', distance_m: 50, style: 'freestyle', gender_rule: 'men', slots: [] },
  { key: '4x100_medley_mixed', label: '4x100 combinado mixto', distance_m: 100, style: 'medley', gender_rule: 'mixed_2f_2m', slots: [] },
  { key: '4x100_medley_women', label: '4x100 combinado mujeres', distance_m: 100, style: 'medley', gender_rule: 'women', slots: [] },
  { key: '4x100_medley_men', label: '4x100 combinado hombres', distance_m: 100, style: 'medley', gender_rule: 'men', slots: [] },
  { key: '4x100_freestyle_mixed', label: '4x100 libre mixto', distance_m: 100, style: 'freestyle', gender_rule: 'mixed_2f_2m', slots: [] },
  { key: '4x100_freestyle_women', label: '4x100 libre mujeres', distance_m: 100, style: 'freestyle', gender_rule: 'women', slots: [] },
  { key: '4x100_freestyle_men', label: '4x100 libre hombres', distance_m: 100, style: 'freestyle', gender_rule: 'men', slots: [] },
];

type EditableRelay = {
  id: string;
  assignments: Record<string, string | null>;
};

type DragPayload = {
  athleteId: string;
  sourceRelayId?: string;
  sourceSlotKey?: string;
};

type ManualTimeResult = {
  ms: number | null;
  error: string | null;
};

function formatTime(ms: number | null): string | null {
  if (ms === null) return null;
  const minutes = Math.floor(ms / 60000);
  const seconds = Math.floor((ms % 60000) / 1000);
  const hundredths = Math.floor((ms % 1000) / 10);
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(hundredths).padStart(2, '0')}`;
}

function parseManualTime(value: string): ManualTimeResult {
  const text = value.trim();
  if (!text) return { ms: null, error: null };
  const match = text.match(/^(?:(\d{1,2}):)?(\d{1,2})(?:[,.](\d{1,2}))?$/);
  if (!match) return { ms: null, error: 'Tiempo manual inválido. Usa 00:30.50 o 30.50.' };
  const minutes = Number(match[1] ?? 0);
  const seconds = Number(match[2]);
  const hundredths = Number((match[3] ?? '0').padEnd(2, '0').slice(0, 2));
  return { ms: ((minutes * 60) + seconds) * 1000 + hundredths * 10, error: null };
}

function categoryFor(ageSum: number | null, categories: RelayAnalysisResponse['categories']) {
  if (ageSum === null) return null;
  return categories.find((category) => ageSum >= category.min_age_sum && ageSum <= category.max_age_sum) ?? null;
}

function assignmentsFromSlots(slots: RelaySlot[]): Record<string, string | null> {
  return Object.fromEntries(slots.map((slot) => [slot.key, null]));
}

function relayFromLineup(lineup: RelayLineup, slots: RelaySlot[]): EditableRelay {
  const assignments = assignmentsFromSlots(slots);
  for (const leg of lineup.legs) assignments[leg.slot_key] = leg.athlete_id;
  return { id: lineup.id, assignments };
}

function emptyRelay(index: number, slots: RelaySlot[]): EditableRelay {
  return { id: `manual-${index}`, assignments: assignmentsFromSlots(slots) };
}

function genderLabel(gender: RelayAthlete['gender'] | null): string {
  if (gender === 'female') return 'F';
  if (gender === 'male') return 'M';
  return 'Sin género';
}

function sourceLabel(source: string | null | undefined): string {
  if (source === 'db') return 'BD';
  if (source === 'excel') return 'Excel';
  if (source === 'manual') return 'Manual';
  return 'Sin marca';
}

function strokeLabel(stroke: string): string {
  const labels: Record<string, string> = {
    backstroke: 'Espalda',
    breaststroke: 'Pecho',
    butterfly: 'Mariposa',
    freestyle: 'Libre',
  };
  return labels[stroke] ?? stroke;
}

function relayOptionLabel(athlete: RelayAthlete, slot: RelaySlot, assignedElsewhere: boolean, unavailable: boolean): string {
  const ageLabel = athlete.age === null ? 'sin edad' : `${athlete.age} años`;
  const time = athlete.times[slot.stroke];
  const timeLabel = time?.text ?? formatTime(time?.ms ?? null) ?? `sin registro en ${slot.stroke_label}`;
  const statusLabels = [assignedElsewhere ? 'ya usado' : null, unavailable ? 'no disponible' : null].filter(Boolean);
  const statusSuffix = statusLabels.length > 0 ? ` — ${statusLabels.join(', ')}` : '';
  return `${athlete.full_name} — ${ageLabel} — ${slot.stroke_label}: ${timeLabel}${statusSuffix}`;
}

function manualTimeKey(relayId: string, slotKey: string): string {
  return `${relayId}:${slotKey}`;
}

function getSlotTimeMs(athlete: RelayAthlete | null, slot: RelaySlot, relayId: string, manualTimes: Record<string, string>) {
  const dbTime = athlete?.times[slot.stroke]?.ms ?? null;
  if (dbTime !== null) return { ms: dbTime, source: athlete?.times[slot.stroke]?.source ?? 'db', error: null };
  const manual = parseManualTime(manualTimes[manualTimeKey(relayId, slot.key)] ?? '');
  return { ms: manual.ms, source: manual.ms !== null ? 'manual' : null, error: manual.error };
}

function evaluateRelay(
  relay: EditableRelay,
  slots: RelaySlot[],
  relayType: RelayType,
  athletesById: Map<string, RelayAthlete>,
  categories: RelayAnalysisResponse['categories'],
  manualTimes: Record<string, string>,
  unavailableAthleteIds: Set<string>,
  assignedIdCounts: Map<string, number>,
) {
  const athletes = slots.map((slot) => {
    const athleteId = relay.assignments[slot.key];
    return athleteId ? athletesById.get(athleteId) ?? null : null;
  });
  const errors: string[] = [];
  const assignedAthletes = athletes.filter((athlete): athlete is RelayAthlete => athlete !== null);
  const assignedIds = assignedAthletes.map((athlete) => athlete.id);

  if (assignedAthletes.length !== slots.length) errors.push('Faltan postas por asignar.');
  if (new Set(assignedIds).size !== assignedIds.length) errors.push('Hay atletas repetidos en el relevo.');
  if (assignedIds.some((id) => (assignedIdCounts.get(id) ?? 0) > 1)) errors.push('Hay atletas considerados en más de un relevo.');
  if (assignedIds.some((id) => unavailableAthleteIds.has(id))) errors.push('Hay atletas marcados como no disponibles para relevos.');

  const women = assignedAthletes.filter((athlete) => athlete.gender === 'female').length;
  const men = assignedAthletes.filter((athlete) => athlete.gender === 'male').length;
  if (relayType.gender_rule === 'mixed_2f_2m' && (women !== 2 || men !== 2)) errors.push('Debe tener exactamente 2 mujeres y 2 hombres.');
  if (relayType.gender_rule === 'women' && women !== 4) errors.push('Debe tener 4 mujeres.');
  if (relayType.gender_rule === 'men' && men !== 4) errors.push('Debe tener 4 hombres.');

  const hasMissingAge = athletes.some((athlete) => !athlete || athlete.age === null);
  if (hasMissingAge) errors.push('Todas las postas deben tener edad válida.');

  const ageSum = hasMissingAge ? null : athletes.reduce((sum, athlete) => sum + (athlete?.age ?? 0), 0);
  const category = categoryFor(ageSum, categories);
  if (ageSum !== null && !category) errors.push('La suma de edades no corresponde a ninguna categoría.');

  const times = slots.map((slot, index) => getSlotTimeMs(athletes[index], slot, relay.id, manualTimes));
  const manualTimeError = times.find((time) => time.error)?.error;
  if (manualTimeError) errors.push(manualTimeError);
  if (times.some((time) => time.ms === null)) errors.push('Hay postas sin mejor tiempo registrado ni tiempo manual para ese estilo.');
  const totalTimeMs = times.every((time) => time.ms !== null) ? times.reduce((sum, time) => sum + (time.ms ?? 0), 0) : null;

  return { isValid: errors.length === 0, errors, category, ageSum, totalTimeMs, totalTimeText: formatTime(totalTimeMs) };
}

function AthleteCard({
  athlete,
  unavailable = false,
  assignedElsewhere = false,
  dragPayload,
  onToggleAvailability,
}: {
  athlete: RelayAthlete;
  unavailable?: boolean;
  assignedElsewhere?: boolean;
  dragPayload?: DragPayload;
  onToggleAvailability?: () => void;
}) {
  return (
    <div
      draggable={Boolean(dragPayload) && !unavailable}
      onDragStart={(event) => {
        if (!dragPayload || unavailable) return;
        event.dataTransfer.setData('application/json', JSON.stringify(dragPayload));
        event.dataTransfer.effectAllowed = 'move';
      }}
      className={`rounded-lg border p-3 shadow-sm ${unavailable ? 'border-red-200 bg-red-50' : assignedElsewhere ? 'border-red-200 bg-red-50/70' : 'border-slate-200 bg-white'} ${dragPayload && !unavailable ? 'cursor-grab active:cursor-grabbing' : ''}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">{athlete.full_name}</p>
          <p className="mt-1 text-xs text-slate-500">
            {genderLabel(athlete.gender)} · {athlete.age ?? 'sin edad'} años · atleta #{athlete.core_athlete_id ?? athlete.id}
          </p>
          {assignedElsewhere && <p className="mt-1 text-xs font-semibold text-red-700">Ya está considerado en otro relevo.</p>}
          {unavailable && <p className="mt-1 text-xs font-semibold text-red-700">Marcado como no disponible.</p>}
        </div>
        {onToggleAvailability && (
          <button type="button" onClick={onToggleAvailability} className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50">
            {unavailable ? 'Habilitar' : 'No disponible'}
          </button>
        )}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-1 text-xs text-slate-600">
        {Object.entries(athlete.times).map(([stroke, time]) => (
          <span key={stroke} className="rounded bg-slate-50 px-2 py-1">
            {strokeLabel(stroke)}: {time.text ?? '—'} <strong>({sourceLabel(time.source)})</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

export const RelaysPage: React.FC = () => {
  const [selectedRelayType, setSelectedRelayType] = React.useState('4x50_medley_mixed');
  const [clubSearch, setClubSearch] = React.useState('');
  const [clubs, setClubs] = React.useState<Club[]>([]);
  const [selectedClub, setSelectedClub] = React.useState<Club | null>(null);
  const [attendanceFile, setAttendanceFile] = React.useState<File | null>(null);
  const [selectedAthleteIds, setSelectedAthleteIds] = React.useState<Set<string>>(new Set());
  const [unavailableAthleteIds, setUnavailableAthleteIds] = React.useState<Set<string>>(new Set());
  const [manualTimes, setManualTimes] = React.useState<Record<string, string>>({});
  const [analysis, setAnalysis] = React.useState<RelayAnalysisResponse | null>(null);
  const [relays, setRelays] = React.useState<EditableRelay[]>([]);
  const [isLoadingClubs, setIsLoadingClubs] = React.useState(false);
  const [isLoadingRoster, setIsLoadingRoster] = React.useState(false);
  const [isAnalyzing, setIsAnalyzing] = React.useState(false);
  const [isAttendanceCollapsed, setIsAttendanceCollapsed] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const relayTypes = analysis?.relay_types ?? DEFAULT_RELAY_TYPES;
  const relayType = analysis?.relay_type ?? relayTypes.find((item) => item.key === selectedRelayType) ?? DEFAULT_RELAY_TYPES[0];
  const slots = analysis?.relay_type.slots ?? [];

  React.useEffect(() => {
    const handler = setTimeout(async () => {
      setIsLoadingClubs(true);
      try {
        const response = await clubService.getClubs(clubSearch, 1);
        setClubs(response.data);
      } catch {
        setClubs([]);
      } finally {
        setIsLoadingClubs(false);
      }
    }, 300);
    return () => clearTimeout(handler);
  }, [clubSearch]);

  const athletesById = React.useMemo(
    () => new Map((analysis?.athletes ?? []).map((athlete) => [athlete.id, athlete])),
    [analysis],
  );

  const assignedIdCounts = React.useMemo(() => {
    const counts = new Map<string, number>();
    for (const id of relays.flatMap((relay) => Object.values(relay.assignments)).filter((value): value is string => value !== null)) {
      counts.set(id, (counts.get(id) ?? 0) + 1);
    }
    return counts;
  }, [relays]);

  const availableAthletes = React.useMemo(
    () => (analysis?.athletes ?? []).filter((athlete) => !assignedIdCounts.has(athlete.id) && !unavailableAthleteIds.has(athlete.id)),
    [analysis, assignedIdCounts, unavailableAthleteIds],
  );

  function resetEditor() {
    setRelays([]);
    setManualTimes({});
  }

  async function loadRoster(club: Club, relayTypeKey: string) {
    setIsLoadingRoster(true);
    setError(null);
    try {
      const result = await relayService.getClubRoster(String(club.id), relayTypeKey);
      setAnalysis(result);
      resetEditor();
      setSelectedAthleteIds(new Set(result.athletes.map((athlete) => athlete.id)));
      setUnavailableAthleteIds(new Set());
      setIsAttendanceCollapsed(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Error inesperado al cargar roster');
      setAnalysis(null);
      resetEditor();
      setSelectedAthleteIds(new Set());
      setUnavailableAthleteIds(new Set());
      setIsAttendanceCollapsed(false);
    } finally {
      setIsLoadingRoster(false);
    }
  }

  async function loadRosterFromAttendance(club: Club, relayTypeKey: string, file: File) {
    setIsLoadingRoster(true);
    setError(null);
    try {
      const result = await relayService.getClubRosterFromAttendance(String(club.id), relayTypeKey, file);
      setAnalysis(result);
      setSelectedAthleteIds(new Set(result.athletes.map((athlete) => athlete.id)));
      setUnavailableAthleteIds((current) => {
        const attendeeIds = new Set(result.athletes.map((athlete) => athlete.id));
        return new Set(Array.from(current).filter((id) => attendeeIds.has(id)));
      });
      resetEditor();
      setIsAttendanceCollapsed(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Error inesperado al filtrar asistentes');
      setAttendanceFile(null);
    } finally {
      setIsLoadingRoster(false);
    }
  }

  async function selectClub(club: Club) {
    setSelectedClub(club);
    setClubSearch(club.name);
    setAttendanceFile(null);
    setIsAttendanceCollapsed(false);
    await loadRoster(club, selectedRelayType);
  }

  async function handleRelayTypeChange(event: React.ChangeEvent<HTMLSelectElement>) {
    const nextType = event.target.value;
    setSelectedRelayType(nextType);
    setIsAttendanceCollapsed(false);
    resetEditor();
    if (!selectedClub) return;
    if (attendanceFile) await loadRosterFromAttendance(selectedClub, nextType, attendanceFile);
    else await loadRoster(selectedClub, nextType);
  }

  function toggleAthlete(athleteId: string) {
    setSelectedAthleteIds((current) => {
      const next = new Set(current);
      if (next.has(athleteId)) next.delete(athleteId);
      else next.add(athleteId);
      return next;
    });
  }

  function toggleAvailability(athleteId: string) {
    setUnavailableAthleteIds((current) => {
      const next = new Set(current);
      if (next.has(athleteId)) next.delete(athleteId);
      else next.add(athleteId);
      return next;
    });
  }

  function selectAllAthletes() {
    setSelectedAthleteIds(new Set((analysis?.athletes ?? []).map((athlete) => athlete.id)));
  }

  function clearSelectedAthletes() {
    setSelectedAthleteIds(new Set());
  }

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    event.target.value = '';
    if (!file || !selectedClub) return;

    setAttendanceFile(file);
    await loadRosterFromAttendance(selectedClub, selectedRelayType, file);
  }

  async function clearAttendanceFilter() {
    setAttendanceFile(null);
    setIsAttendanceCollapsed(false);
    resetEditor();
    if (selectedClub) await loadRoster(selectedClub, selectedRelayType);
  }

  async function runAnalysis() {
    if (!selectedClub) {
      setError('Primero seleccione un club.');
      return;
    }
    const eligibleAthleteIds = Array.from(selectedAthleteIds).filter((id) => !unavailableAthleteIds.has(id));
    if (eligibleAthleteIds.length < 4) {
      setError('Seleccione al menos 4 asistentes disponibles para relevos.');
      return;
    }
    setIsAnalyzing(true);
    setError(null);
    try {
      const result = await relayService.analyzeEntries(selectedRelayType, {
        clubId: String(selectedClub.id),
        file: attendanceFile ?? undefined,
        athleteIds: eligibleAthleteIds,
      });
      setAnalysis(result);
      setSelectedAthleteIds(new Set(result.athletes.map((athlete) => athlete.id)));
      setRelays(result.proposal.map((lineup) => relayFromLineup(lineup, result.relay_type.slots)));
      setManualTimes({});
      setIsAttendanceCollapsed(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Error inesperado al analizar relevos');
      resetEditor();
    } finally {
      setIsAnalyzing(false);
    }
  }

  function setSlotAssignment(targetRelayId: string, targetSlotKey: string, athleteId: string | null) {
    setRelays((current) => current.map((relay) => (
      relay.id === targetRelayId ? { ...relay, assignments: { ...relay.assignments, [targetSlotKey]: athleteId } } : relay
    )));
  }

  function swapSlots(targetRelayId: string, targetSlotKey: string, payload: DragPayload) {
    setRelays((current) => {
      if (!payload.sourceRelayId || !payload.sourceSlotKey) {
        return current.map((relay) => (
          relay.id === targetRelayId ? { ...relay, assignments: { ...relay.assignments, [targetSlotKey]: payload.athleteId } } : relay
        ));
      }
      if (payload.sourceRelayId === targetRelayId && payload.sourceSlotKey === targetSlotKey) return current;

      const sourceRelayId = payload.sourceRelayId;
      const sourceSlotKey = payload.sourceSlotKey;
      const sourceRelay = current.find((relay) => relay.id === sourceRelayId);
      const targetRelay = current.find((relay) => relay.id === targetRelayId);
      if (!sourceRelay || !targetRelay) return current;

      const sourceValue = sourceRelay.assignments[sourceSlotKey] ?? null;
      const targetValue = targetRelay.assignments[targetSlotKey] ?? null;

      return current.map((relay) => {
        if (relay.id === sourceRelayId && relay.id === targetRelayId) {
          return { ...relay, assignments: { ...relay.assignments, [sourceSlotKey]: targetValue, [targetSlotKey]: sourceValue } };
        }
        if (relay.id === sourceRelayId) {
          return { ...relay, assignments: { ...relay.assignments, [sourceSlotKey]: targetValue } };
        }
        if (relay.id === targetRelayId) {
          return { ...relay, assignments: { ...relay.assignments, [targetSlotKey]: sourceValue } };
        }
        return relay;
      });
    });

    if (payload.sourceRelayId && payload.sourceSlotKey) {
      const sourceManualKey = manualTimeKey(payload.sourceRelayId, payload.sourceSlotKey);
      const targetManualKey = manualTimeKey(targetRelayId, targetSlotKey);
      setManualTimes((current) => {
        const sourceManualTime = current[sourceManualKey];
        const targetManualTime = current[targetManualKey];
        const next = { ...current };
        if (targetManualTime) next[sourceManualKey] = targetManualTime;
        else delete next[sourceManualKey];
        if (sourceManualTime) next[targetManualKey] = sourceManualTime;
        else delete next[targetManualKey];
        return next;
      });
    }
  }

  function clearLeg(relayId: string, slotKey: string) {
    setRelays((current) => current.map((relay) => (
      relay.id === relayId ? { ...relay, assignments: { ...relay.assignments, [slotKey]: null } } : relay
    )));
    setManualTimes((current) => {
      const next = { ...current };
      delete next[manualTimeKey(relayId, slotKey)];
      return next;
    });
  }

  function handleDrop(event: React.DragEvent, relayId: string, slotKey: string) {
    event.preventDefault();
    const rawPayload = event.dataTransfer.getData('application/json');
    if (!rawPayload) return;
    const payload = JSON.parse(rawPayload) as DragPayload;
    swapSlots(relayId, slotKey, payload);
  }

  function isAssignedElsewhere(athleteId: string, relayId: string, slotKey: string) {
    return relays.some((relay) => Object.entries(relay.assignments).some(([currentSlotKey, currentAthleteId]) => (
      currentAthleteId === athleteId && (relay.id !== relayId || currentSlotKey !== slotKey)
    )));
  }

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 to-white p-6 shadow-sm">
        <div className="space-y-3">
          <p className="text-sm font-semibold uppercase tracking-wide text-blue-700">Organizador de relevos</p>
          <ol className="grid gap-2 text-sm text-slate-600 sm:grid-cols-4">
            <li className="rounded-lg bg-white/70 px-3 py-2"><span className="font-semibold text-blue-700">1.</span> Seleccione un club</li>
            <li className="rounded-lg bg-white/70 px-3 py-2"><span className="font-semibold text-blue-700">2.</span> Seleccione tipo de relevo a analizar</li>
            <li className="rounded-lg bg-white/70 px-3 py-2"><span className="font-semibold text-blue-700">3.</span> Seleccione asistentes o cargue Excel de inscripción</li>
            <li className="rounded-lg bg-white/70 px-3 py-2"><span className="font-semibold text-blue-700">4.</span> Ejecute el análisis</li>
          </ol>
        </div>

        <div className="mt-6 grid gap-3 lg:grid-cols-[minmax(0,1fr)_260px_auto_auto]">
          <div className="relative">
            <input
              value={clubSearch}
              onChange={(event) => {
                setClubSearch(event.target.value);
                setSelectedClub(null);
                setAnalysis(null);
                resetEditor();
                setSelectedAthleteIds(new Set());
                setUnavailableAthleteIds(new Set());
              }}
              placeholder="Buscar club vigente..."
              className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500"
            />
            {!selectedClub && clubSearch && (
              <div className="absolute z-20 mt-2 max-h-72 w-full overflow-auto rounded-xl border border-slate-200 bg-white shadow-lg">
                {isLoadingClubs ? <p className="p-3 text-sm text-slate-500">Buscando clubes...</p> : clubs.map((club) => (
                  <button key={String(club.id)} type="button" onClick={() => void selectClub(club)} className="block w-full px-4 py-3 text-left text-sm hover:bg-blue-50">
                    <span className="font-semibold text-slate-900">{club.name}</span>
                    <span className="ml-2 text-slate-500">{club.total_athletes ?? 0} atletas</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <select value={selectedRelayType} onChange={handleRelayTypeChange} className="rounded-xl border border-slate-300 bg-white px-4 py-3 text-sm font-medium text-slate-700 shadow-sm">
            {relayTypes.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
          </select>

          <label className={`inline-flex items-center justify-center rounded-xl px-5 py-3 text-sm font-semibold shadow-sm transition ${selectedClub ? 'cursor-pointer border border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100' : 'cursor-not-allowed bg-slate-200 text-slate-500'}`}>
            Cargar Excel
            <input type="file" accept=".xlsx,.xlsm" className="hidden" onChange={handleFileChange} disabled={!selectedClub || isAnalyzing} />
          </label>

          <button type="button" onClick={() => void runAnalysis()} disabled={!selectedClub || isAnalyzing || isLoadingRoster} className="rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300">
            {isAnalyzing ? 'Analizando...' : 'Analizar relevos'}
          </button>
        </div>

        {selectedClub && attendanceFile && (
          <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700">
            <span>Excel de asistencia cargado: <strong>{attendanceFile.name}</strong></span>
            <button type="button" onClick={clearAttendanceFilter} className="font-semibold text-emerald-800 underline underline-offset-4">
              Quitar Excel
            </button>
          </div>
        )}
      </div>

      {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}
      {isLoadingRoster && <div className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-700">Cargando roster vigente del club...</div>}

      {analysis && selectedClub && (
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900">Asistentes</h2>
              <p className="text-sm text-slate-500">
                Club: {selectedClub.name}. {analysis.athletes.length} asistentes cargados, {unavailableAthleteIds.size} no disponibles para relevos.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {isAttendanceCollapsed && (
                <button type="button" onClick={() => setIsAttendanceCollapsed(false)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700">
                  Editar asistentes
                </button>
              )}
              {!isAttendanceCollapsed && (
                <>
                  <button type="button" onClick={selectAllAthletes} disabled={Boolean(attendanceFile)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 disabled:opacity-50">Todos</button>
                  <button type="button" onClick={clearSelectedAthletes} disabled={Boolean(attendanceFile)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 disabled:opacity-50">Ninguno</button>
                </>
              )}
              {attendanceFile && <button type="button" onClick={clearAttendanceFilter} className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700">Quitar Excel</button>}
            </div>
          </div>

          {attendanceFile && (
            <p className="mt-3 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700">Excel cargado: {attendanceFile.name}. El análisis usará solo asistentes encontrados en ese archivo y excluirá a los no disponibles.</p>
          )}

          {!isAttendanceCollapsed && (
            <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {analysis.athletes.map((athlete) => (
                <label key={athlete.id} className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 hover:bg-slate-50 ${unavailableAthleteIds.has(athlete.id) ? 'border-red-200 bg-red-50' : 'border-slate-200'}`}>
                  <input type="checkbox" checked={selectedAthleteIds.has(athlete.id)} onChange={() => toggleAthlete(athlete.id)} disabled={Boolean(attendanceFile)} className="mt-1" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold text-slate-900">{athlete.full_name}</span>
                    <span className="text-xs text-slate-500">{genderLabel(athlete.gender)} · {athlete.age ?? 'sin edad'} años</span>
                    {unavailableAthleteIds.has(athlete.id) && <span className="block text-xs font-semibold text-red-700">No disponible para relevos</span>}
                  </span>
                  <button type="button" onClick={(event) => { event.preventDefault(); toggleAvailability(athlete.id); }} className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50">
                    {unavailableAthleteIds.has(athlete.id) ? 'Habilitar' : 'No relevo'}
                  </button>
                </label>
              ))}
            </div>
          )}
        </div>
      )}

      {analysis && relays.length > 0 && (
        <div className="space-y-4">
          <section className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Propuesta y edición manual</h2>
                <p className="text-sm text-slate-500">{relays.length} relevos en tablero · {availableAthletes.length} atletas disponibles</p>
              </div>
              <button type="button" onClick={() => setRelays((current) => [...current, emptyRelay(current.length + 1, slots)])} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm hover:bg-slate-50">Agregar relevo manual</button>
            </div>

            {relays.map((relay, index) => {
              const evaluation = evaluateRelay(relay, slots, relayType, athletesById, analysis.categories, manualTimes, unavailableAthleteIds, assignedIdCounts);
              return (
                <article key={relay.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                    <div>
                      <h3 className="text-lg font-semibold text-slate-900">Relevo {index + 1}</h3>
                      <p className="text-sm text-slate-500">{evaluation.category ? `Categoría ${evaluation.category.label}` : 'Sin categoría'} · suma edades {evaluation.ageSum ?? 'sin datos'}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`rounded-full px-3 py-1 text-sm font-semibold ${evaluation.isValid ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>{evaluation.isValid ? 'Válido' : 'Revisar'}</span>
                      <span className="rounded-full bg-blue-50 px-3 py-1 text-sm font-semibold text-blue-700">{evaluation.totalTimeText ?? 'sin tiempo'}</span>
                    </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-4">
                    {slots.map((slot) => {
                      const athleteId = relay.assignments[slot.key];
                      const athlete = athleteId ? athletesById.get(athleteId) ?? null : null;
                      const rawTime = athlete?.times[slot.stroke] ?? null;
                      const resolvedTime = getSlotTimeMs(athlete, slot, relay.id, manualTimes);
                      const slotManualKey = manualTimeKey(relay.id, slot.key);
                      return (
                        <div key={slot.key} onDragOver={(event) => event.preventDefault()} onDrop={(event) => handleDrop(event, relay.id, slot.key)} className="min-h-36 rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 p-3 transition hover:border-blue-300 hover:bg-blue-50/50">
                          <div className="mb-2 flex items-center justify-between">
                            <p className="text-sm font-semibold text-slate-700">{slot.label}</p>
                            {athlete && <button type="button" onClick={() => clearLeg(relay.id, slot.key)} className="text-xs font-medium text-slate-400 hover:text-red-600">Quitar</button>}
                          </div>

                          <select
                            value={athleteId ?? ''}
                            onChange={(event) => setSlotAssignment(relay.id, slot.key, event.target.value || null)}
                            className="mb-3 w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-700"
                          >
                            <option value="">Seleccionar atleta...</option>
                            {(analysis.athletes ?? []).map((optionAthlete) => {
                              const assignedElsewhere = isAssignedElsewhere(optionAthlete.id, relay.id, slot.key);
                              const unavailable = unavailableAthleteIds.has(optionAthlete.id);
                              return (
                                <option key={optionAthlete.id} value={optionAthlete.id} className={assignedElsewhere || unavailable ? 'bg-red-50 text-red-700' : undefined}>
                                  {relayOptionLabel(optionAthlete, slot, assignedElsewhere, unavailable)}
                                </option>
                              );
                            })}
                          </select>

                          {athlete ? (
                            <AthleteCard
                              athlete={athlete}
                              unavailable={unavailableAthleteIds.has(athlete.id)}
                              assignedElsewhere={isAssignedElsewhere(athlete.id, relay.id, slot.key)}
                              dragPayload={{ athleteId: athlete.id, sourceRelayId: relay.id, sourceSlotKey: slot.key }}
                            />
                          ) : <div className="flex h-24 items-center justify-center rounded-lg border border-slate-200 bg-white text-center text-sm text-slate-400">Seleccione o arrastre a un atleta</div>}

                          <p className={`mt-2 text-xs ${resolvedTime.ms !== null ? 'text-slate-500' : 'text-amber-600'}`}>{slot.stroke_label}: {formatTime(resolvedTime.ms) ?? rawTime?.text ?? 'sin marca'} · {sourceLabel(resolvedTime.source)}</p>
                          {athlete && rawTime?.ms === null && (
                            <input
                              value={manualTimes[slotManualKey] ?? ''}
                              onChange={(event) => setManualTimes((current) => ({ ...current, [slotManualKey]: event.target.value }))}
                              placeholder="Tiempo manual ej. 00:35.20"
                              className="mt-2 w-full rounded-lg border border-amber-200 bg-white px-2 py-2 text-xs text-slate-700 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-200"
                            />
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {evaluation.errors.length > 0 && <ul className="mt-4 space-y-1 rounded-xl bg-amber-50 p-3 text-sm text-amber-800">{evaluation.errors.map((item) => <li key={item}>• {item}</li>)}</ul>}
                </article>
              );
            })}
          </section>

        </div>
      )}
    </div>
  );
};
