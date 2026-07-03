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
const EMPTY_RELAY_SLOTS: RelaySlot[] = [];

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

function assignedAthleteIdsFromRelays(relays: EditableRelay[]): Set<string> {
  return new Set(relays.flatMap((relay) => Object.values(relay.assignments)).filter((value): value is string => value !== null));
}

function relayCategoryKey(
  relay: EditableRelay,
  slots: RelaySlot[],
  athletesById: Map<string, RelayAthlete>,
  categories: RelayAnalysisResponse['categories'],
): string | null {
  const athletes = slots.map((slot) => {
    const athleteId = relay.assignments[slot.key];
    return athleteId ? athletesById.get(athleteId) ?? null : null;
  });
  if (athletes.some((athlete) => !athlete || athlete.age === null)) return null;
  const ageSum = athletes.reduce((sum, athlete) => sum + (athlete?.age ?? 0), 0);
  return categoryFor(ageSum, categories)?.key ?? null;
}

function mergeRelayAthletes(current: RelayAthlete[], incoming: RelayAthlete[]): RelayAthlete[] {
  const byId = new Map(current.map((athlete) => [athlete.id, athlete]));
  for (const athlete of incoming) byId.set(athlete.id, athlete);
  return Array.from(byId.values());
}

function keepManualTimesForRelays(manualTimes: Record<string, string>, relays: EditableRelay[], slots: RelaySlot[]): Record<string, string> {
  const keysToKeep = new Set(relays.flatMap((relay) => slots.map((slot) => manualTimeKey(relay.id, slot.key))));
  return Object.fromEntries(Object.entries(manualTimes).filter(([key]) => keysToKeep.has(key)));
}

function genderLabel(gender: RelayAthlete['gender'] | null): string {
  if (gender === 'female') return 'F';
  if (gender === 'male') return 'M';
  return 'Sin género';
}

function isAthleteAllowedByRelayGender(athlete: RelayAthlete, relayType: RelayType): boolean {
  if (relayType.gender_rule === 'women') return athlete.gender === 'female';
  if (relayType.gender_rule === 'men') return athlete.gender === 'male';
  return true;
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
  const ageLabel = athlete.age === null ? 's/e' : `${athlete.age}a`;
  const time = athlete.times[slot.stroke];
  const timeLabel = time?.text ?? formatTime(time?.ms ?? null) ?? 'sin marca';
  const statusLabels = [assignedElsewhere ? 'ya usado' : null, unavailable ? 'no disponible' : null].filter(Boolean);
  const statusSuffix = statusLabels.length > 0 ? ` (${statusLabels.join(', ')})` : '';
  return `${athlete.full_name} | ${ageLabel} | ${timeLabel}${statusSuffix}`;
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
  categoryKeyCounts: Map<string, number>,
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
  if (category && (categoryKeyCounts.get(category.key) ?? 0) > 1) errors.push('Ya existe otro relevo en la misma categoría de edad.');

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
  consideredStroke,
  consideredTimeText,
  consideredTimeSource,
  consideredTimeInput,
}: {
  athlete: RelayAthlete;
  unavailable?: boolean;
  assignedElsewhere?: boolean;
  dragPayload?: DragPayload;
  onToggleAvailability?: () => void;
  consideredStroke?: string;
  consideredTimeText?: string | null;
  consideredTimeSource?: string | null;
  consideredTimeInput?: React.ReactNode;
}) {
  return (
    <div
      draggable={Boolean(dragPayload) && !unavailable}
      onDragStart={(event) => {
        if (!dragPayload || unavailable) return;
        event.dataTransfer.setData('application/json', JSON.stringify(dragPayload));
        event.dataTransfer.effectAllowed = 'move';
      }}
      className={`rounded-lg border p-2 shadow-sm sm:p-3 ${unavailable ? 'border-red-200 bg-red-50' : assignedElsewhere ? 'border-red-200 bg-red-50/70' : 'border-slate-200 bg-white'} ${dragPayload && !unavailable ? 'cursor-grab active:cursor-grabbing' : ''}`}
    >
      <div className="flex items-start justify-between gap-2 sm:gap-3">
        <div className="min-w-0">
          <p className="truncate text-xs font-semibold text-slate-900 sm:text-sm">{athlete.full_name}</p>
          <p className="mt-1 text-[11px] text-slate-500 sm:text-xs">
            {genderLabel(athlete.gender)} · {athlete.age ?? 'sin edad'} años <span className="hidden sm:inline">· atleta #{athlete.core_athlete_id ?? athlete.id}</span>
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
      <div className="mt-2 grid grid-cols-1 gap-1 text-[11px] text-slate-600 sm:mt-3 sm:grid-cols-2 sm:text-xs">
        {Object.entries(athlete.times).map(([stroke, time]) => {
          const isConsidered = stroke === consideredStroke;
          const displayTime = isConsidered ? (consideredTimeText ?? time.text ?? '') : (time.text ?? '');
          const displaySource = isConsidered ? (consideredTimeSource ?? time.source) : time.source;
          return (
            <div
              key={stroke}
              className={`rounded border px-2 py-1 ${!isConsidered ? 'hidden sm:block' : ''} ${
                isConsidered
                  ? 'border-blue-300 bg-blue-50 font-semibold text-blue-800 ring-1 ring-blue-100'
                  : 'border-transparent bg-slate-50 text-slate-600'
              }`}
            >
              {strokeLabel(stroke)}: {displayTime} <strong>({sourceLabel(displaySource)})</strong>
              {isConsidered && consideredTimeInput}
            </div>
          );
        })}
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
  const [fixedRelayIds, setFixedRelayIds] = React.useState<Set<string>>(new Set());
  const [isLoadingClubs, setIsLoadingClubs] = React.useState(false);
  const [isLoadingRoster, setIsLoadingRoster] = React.useState(false);
  const [isAnalyzing, setIsAnalyzing] = React.useState(false);
  const [isSetupCollapsed, setIsSetupCollapsed] = React.useState(false);
  const [isAttendanceCollapsed, setIsAttendanceCollapsed] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [toastMessage, setToastMessage] = React.useState<string | null>(null);

  const relayTypes = analysis?.relay_types ?? DEFAULT_RELAY_TYPES;
  const relayType = analysis?.relay_type ?? relayTypes.find((item) => item.key === selectedRelayType) ?? DEFAULT_RELAY_TYPES[0];
  const slots = analysis?.relay_type.slots ?? EMPTY_RELAY_SLOTS;

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

  React.useEffect(() => {
    if (!toastMessage) return undefined;
    const handler = window.setTimeout(() => setToastMessage(null), 5000);
    return () => window.clearTimeout(handler);
  }, [toastMessage]);

  function showToast(message: string) {
    setToastMessage(message);
  }

  const athletesById = React.useMemo(
    () => new Map((analysis?.athletes ?? []).map((athlete) => [athlete.id, athlete])),
    [analysis],
  );

  const genderEligibleAthletes = React.useMemo(
    () => (analysis?.athletes ?? []).filter((athlete) => isAthleteAllowedByRelayGender(athlete, relayType)),
    [analysis, relayType],
  );

  const assignedIdCounts = React.useMemo(() => {
    const counts = new Map<string, number>();
    for (const id of relays.flatMap((relay) => Object.values(relay.assignments)).filter((value): value is string => value !== null)) {
      counts.set(id, (counts.get(id) ?? 0) + 1);
    }
    return counts;
  }, [relays]);

  const fixedRelays = React.useMemo(
    () => relays.filter((relay) => fixedRelayIds.has(relay.id)),
    [relays, fixedRelayIds],
  );

  const fixedAthleteIds = React.useMemo(
    () => assignedAthleteIdsFromRelays(fixedRelays),
    [fixedRelays],
  );

  const fixedCategoryKeys = React.useMemo(
    () => new Set(fixedRelays.map((relay) => relayCategoryKey(relay, slots, athletesById, analysis?.categories ?? [])).filter((key): key is string => key !== null)),
    [fixedRelays, slots, athletesById, analysis],
  );

  const categoryKeyCounts = React.useMemo(() => {
    const counts = new Map<string, number>();
    for (const relay of relays) {
      const categoryKey = relayCategoryKey(relay, slots, athletesById, analysis?.categories ?? []);
      if (categoryKey) counts.set(categoryKey, (counts.get(categoryKey) ?? 0) + 1);
    }
    return counts;
  }, [relays, slots, athletesById, analysis]);

  const availableAthletes = React.useMemo(
    () => genderEligibleAthletes.filter((athlete) => !assignedIdCounts.has(athlete.id) && !unavailableAthleteIds.has(athlete.id)),
    [genderEligibleAthletes, assignedIdCounts, unavailableAthleteIds],
  );

  function resetEditor() {
    setRelays([]);
    setManualTimes({});
    setFixedRelayIds(new Set());
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
      setIsSetupCollapsed(false);
      setIsAttendanceCollapsed(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Error inesperado al cargar roster');
      setAnalysis(null);
      resetEditor();
      setSelectedAthleteIds(new Set());
      setUnavailableAthleteIds(new Set());
      setIsSetupCollapsed(false);
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
      setIsSetupCollapsed(false);
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
    setIsSetupCollapsed(false);
    setIsAttendanceCollapsed(false);
    await loadRoster(club, selectedRelayType);
  }

  async function handleRelayTypeChange(event: React.ChangeEvent<HTMLSelectElement>) {
    const nextType = event.target.value;
    setSelectedRelayType(nextType);
    setIsSetupCollapsed(false);
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
    setSelectedAthleteIds(new Set(genderEligibleAthletes.map((athlete) => athlete.id)));
  }

  function clearSelectedAthletes() {
    setSelectedAthleteIds(new Set());
  }

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    event.target.value = '';
    if (!file || !selectedClub) return;

    setAttendanceFile(file);
    setIsSetupCollapsed(false);
    await loadRosterFromAttendance(selectedClub, selectedRelayType, file);
  }

  async function clearAttendanceFilter() {
    setAttendanceFile(null);
    setIsSetupCollapsed(false);
    setIsAttendanceCollapsed(false);
    resetEditor();
    if (selectedClub) await loadRoster(selectedClub, selectedRelayType);
  }

  async function runAnalysis() {
    if (!selectedClub) {
      setError('Primero seleccione un club.');
      return;
    }
    const genderEligibleIds = new Set(genderEligibleAthletes.map((athlete) => athlete.id));
    const eligibleAthleteIds = Array.from(selectedAthleteIds).filter((id) => genderEligibleIds.has(id) && !unavailableAthleteIds.has(id));
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
      setFixedRelayIds(new Set());
      setIsSetupCollapsed(true);
      setIsAttendanceCollapsed(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Error inesperado al analizar relevos');
      resetEditor();
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function rerunUnlockedAnalysis() {
    if (!selectedClub || !analysis) {
      showToast('Primero ejecute un análisis.');
      return;
    }
    if (fixedRelays.length === 0) {
      showToast('Fije al menos un relevo antes de reanalizar los restantes.');
      return;
    }

    const genderEligibleIds = new Set(genderEligibleAthletes.map((athlete) => athlete.id));
    const eligibleAthleteIds = Array.from(selectedAthleteIds).filter((id) => (
      genderEligibleIds.has(id) && !unavailableAthleteIds.has(id) && !fixedAthleteIds.has(id)
    ));
    if (eligibleAthleteIds.length < 4) {
      showToast('No hay al menos 4 atletas disponibles fuera de los relevos fijados.');
      return;
    }

    setIsAnalyzing(true);
    setError(null);
    try {
      const result = await relayService.analyzeEntries(selectedRelayType, {
        clubId: String(selectedClub.id),
        file: attendanceFile ?? undefined,
        athleteIds: eligibleAthleteIds,
        excludedCategoryKeys: Array.from(fixedCategoryKeys),
      });
      const reanalysisId = Date.now();
      const unlockedRelays = result.proposal.map((lineup, index) => ({
        ...relayFromLineup(lineup, result.relay_type.slots),
        id: `reanalyzed-${reanalysisId}-${index + 1}`,
      }));

      setAnalysis((current) => ({
        ...result,
        athletes: mergeRelayAthletes(current?.athletes ?? [], result.athletes),
      }));
      setRelays([...fixedRelays, ...unlockedRelays]);
      setManualTimes((current) => keepManualTimesForRelays(current, fixedRelays, slots));
      setIsAttendanceCollapsed(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Error inesperado al reanalizar relevos');
    } finally {
      setIsAnalyzing(false);
    }
  }

  function toggleFixedRelay(relayId: string) {
    if (!fixedRelayIds.has(relayId)) {
      const relayToFix = relays.find((relay) => relay.id === relayId);
      if (!relayToFix || !analysis) return;
      const evaluation = evaluateRelay(relayToFix, slots, relayType, athletesById, analysis.categories, manualTimes, unavailableAthleteIds, assignedIdCounts, categoryKeyCounts);
      if (!evaluation.isValid) {
        showToast(`No se puede fijar un relevo inválido: ${evaluation.errors[0] ?? 'revise la composición del relevo.'}`);
        return;
      }
      const categoryToFix = relayCategoryKey(relayToFix, slots, athletesById, analysis.categories);
      if (categoryToFix && fixedCategoryKeys.has(categoryToFix)) {
        showToast('Ya existe un relevo fijado en esa categoría de edad.');
        return;
      }
    }
    setFixedRelayIds((current) => {
      const next = new Set(current);
      if (next.has(relayId)) next.delete(relayId);
      else next.add(relayId);
      return next;
    });
  }

  function setSlotAssignment(targetRelayId: string, targetSlotKey: string, athleteId: string | null) {
    if (fixedRelayIds.has(targetRelayId)) return;
    setRelays((current) => current.map((relay) => (
      relay.id === targetRelayId ? { ...relay, assignments: { ...relay.assignments, [targetSlotKey]: athleteId } } : relay
    )));
  }

  function swapSlots(targetRelayId: string, targetSlotKey: string, payload: DragPayload) {
    if (fixedRelayIds.has(targetRelayId) || (payload.sourceRelayId && fixedRelayIds.has(payload.sourceRelayId))) return;
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
    if (fixedRelayIds.has(relayId)) return;
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
      {toastMessage && (
        <div className="fixed inset-x-4 bottom-24 z-[60] rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm font-medium text-amber-800 shadow-lg sm:inset-x-auto sm:bottom-4 sm:right-4 sm:max-w-md">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-700">!</span>
            <p className="flex-1">{toastMessage}</p>
            <button type="button" onClick={() => setToastMessage(null)} className="text-amber-700 hover:text-amber-900" aria-label="Cerrar alerta">
              ×
            </button>
          </div>
        </div>
      )}
      <div className="rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 to-white p-6 shadow-sm">
        {isSetupCollapsed && selectedClub ? (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm font-semibold uppercase tracking-wide text-blue-700">Organizador de relevos</p>
              <p className="mt-1 text-sm text-slate-600">
                {selectedClub.name} · {relayType.label}
              </p>
            </div>
            <button type="button" onClick={() => setIsSetupCollapsed(false)} className="rounded-lg border border-blue-200 bg-white px-4 py-2 text-sm font-semibold text-blue-700 shadow-sm cursor-pointer hover:bg-blue-50">
              Editar configuración
            </button>
          </div>
        ) : (
          <>
            <div className="space-y-3">
              <p className="text-sm font-semibold uppercase tracking-wide text-blue-700">Organizador de relevos</p>
              <ol className="grid gap-2 text-sm text-slate-600 sm:grid-cols-4">
                <li className="rounded-lg bg-white/70 px-3 py-2"><span className="font-semibold text-blue-700">1.</span> Seleccione un club</li>
                <li className="rounded-lg bg-white/70 px-3 py-2"><span className="font-semibold text-blue-700">2.</span> Seleccione tipo de relevo a analizar</li>
                <li className="rounded-lg bg-white/70 px-3 py-2"><span className="font-semibold text-blue-700">3.</span> Revise asistentes o cargue Excel en la sección siguiente</li>
                <li className="rounded-lg bg-white/70 px-3 py-2"><span className="font-semibold text-blue-700">4.</span> Ejecute el análisis</li>
              </ol>
            </div>

            <div className="mt-6 grid gap-3 lg:grid-cols-[minmax(0,1fr)_260px_auto]">
              <div className="relative">
                <input
                  value={clubSearch}
                  onChange={(event) => {
                    setClubSearch(event.target.value);
                    setSelectedClub(null);
                    setAnalysis(null);
                    setIsSetupCollapsed(false);
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

              <button type="button" onClick={() => void runAnalysis()} disabled={!selectedClub || isAnalyzing || isLoadingRoster} className="rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300 cursor-pointer">
                {isAnalyzing ? 'Analizando...' : 'Analizar relevos'}
              </button>
            </div>
          </>
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
                Club: {selectedClub.name}. {analysis.athletes.length} asistentes cargados, {genderEligibleAthletes.length} compatibles con este relevo, {unavailableAthleteIds.size} no disponibles para relevos.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {isAttendanceCollapsed && (
                <button type="button" onClick={() => setIsAttendanceCollapsed(false)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 cursor-pointer hover:bg-slate-50">
                  Editar asistentes
                </button>
              )}
              {!isAttendanceCollapsed && (
                <>
                  <label className="inline-flex cursor-pointer items-center justify-center rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100">
                    {attendanceFile ? "Reemplazar Excel" : "Cargar Excel"}
                    <input type="file" accept=".xlsx,.xlsm" className="hidden" onChange={handleFileChange} disabled={isAnalyzing} />
                  </label>
                  {attendanceFile && <button type="button" onClick={clearAttendanceFilter} className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-700 cursor-pointer hover:bg-red-100">Quitar Excel</button>}
                  {!attendanceFile && (
                    <>
                      <button type="button" onClick={selectAllAthletes} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 cursor-pointer hover:bg-blue-100">Todos</button>
                      <button type="button" onClick={clearSelectedAthletes} className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 cursor-pointer hover:bg-blue-100">Ninguno</button>
                    </>
                  )}
                </>
              )}
            </div>
          </div>

          {attendanceFile && (
            <div className="mt-3 flex flex-wrap items-center gap-3 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700">
              <span>Excel de asistencia cargado: <strong>{attendanceFile.name}</strong></span>
              <span className="text-emerald-700">El análisis usará solo asistentes encontrados en ese archivo y excluirá a los no disponibles.</span>
            </div>
          )}

          {!attendanceFile && !isAttendanceCollapsed && (
            <p className="mt-3 rounded-lg border border-dashed border-blue-200 bg-blue-50/50 p-3 text-sm text-blue-700">
              Puede seleccionar asistentes manualmente o cargar la planilla de inscripción en formato Excel para limitar el listado a los inscritos confirmados.
            </p>
          )}

          {!isAttendanceCollapsed && (
            <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {genderEligibleAthletes.map((athlete) => (
                <label key={athlete.id} className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 hover:bg-slate-50 ${unavailableAthleteIds.has(athlete.id) ? 'border-red-200 bg-red-50' : 'border-slate-200'}`}>
                  <input type="checkbox" checked={selectedAthleteIds.has(athlete.id)} onChange={() => toggleAthlete(athlete.id)} disabled={Boolean(attendanceFile)} className="mt-1" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold text-slate-900">{athlete.full_name}</span>
                    <span className="text-xs text-slate-500">{genderLabel(athlete.gender)} · {athlete.age ?? 'sin edad'} años</span>
                    {unavailableAthleteIds.has(athlete.id) && <span className="block text-xs font-semibold text-red-700">No disponible para relevos</span>}
                  </span>
                  <button type="button" onClick={(event) => { event.preventDefault(); toggleAvailability(athlete.id); }} className={`rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 ${unavailableAthleteIds.has(athlete.id) ? 'hover:bg-blue-50' : 'hover:bg-red-50'} `}>
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
                <p className="text-sm text-slate-500">{relays.length} relevos en tablero · {fixedRelays.length} fijados · {availableAthletes.length} atletas disponibles</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={() => void rerunUnlockedAnalysis()} disabled={isAnalyzing || fixedRelays.length === 0} className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 shadow-sm hover:bg-blue-100 disabled:cursor-not-allowed disabled:border-slate-200 disabled:bg-slate-100 disabled:text-slate-400">
                  {isAnalyzing ? 'Reanalizando...' : 'Reanalizar no fijados'}
                </button>
                <button type="button" onClick={() => setRelays((current) => [...current, emptyRelay(current.length + 1, slots)])} className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm cursor-pointer hover:bg-slate-50">Agregar relevo manual</button>
              </div>
            </div>

            {relays.map((relay, index) => {
              const evaluation = evaluateRelay(relay, slots, relayType, athletesById, analysis.categories, manualTimes, unavailableAthleteIds, assignedIdCounts, categoryKeyCounts);
              const isFixed = fixedRelayIds.has(relay.id);
              return (
                <article key={relay.id} className={`rounded-2xl border bg-white p-3 shadow-sm sm:p-4 ${isFixed ? 'border-blue-300 ring-1 ring-blue-100' : 'border-slate-200'}`}>
                  <div className="mb-3 flex flex-col gap-2 md:mb-4 md:flex-row md:items-center md:justify-between">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-base font-semibold text-slate-900 sm:text-lg">Relevo {index + 1}</h3>
                        {isFixed && <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700">Fijado</span>}
                      </div>
                      <p className="text-xs text-slate-500 sm:text-sm">{evaluation.category ? `Categoría ${evaluation.category.label}` : 'Sin categoría'} · suma edades {evaluation.ageSum ?? 'sin datos'}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-2 py-1 text-xs font-semibold sm:px-3 sm:text-sm ${evaluation.isValid ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>{evaluation.isValid ? 'Válido' : 'Revisar'}</span>
                      <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700 sm:px-3 sm:text-sm">{evaluation.totalTimeText ?? 'sin tiempo'}</span>
                      <button type="button" onClick={() => toggleFixedRelay(relay.id)} className={`cursor-pointer rounded-full px-2 py-1 text-xs font-semibold sm:px-3 sm:text-sm ${isFixed ? 'bg-slate-100 text-slate-700 hover:bg-slate-200' : 'bg-blue-600 text-white hover:bg-blue-700'}`}>
                        {isFixed ? 'Liberar' : 'Fijar'}
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2 md:grid-cols-4 md:gap-3">
                    {slots.map((slot) => {
                      const athleteId = relay.assignments[slot.key];
                      const athlete = athleteId ? athletesById.get(athleteId) ?? null : null;
                      const rawTime = athlete?.times[slot.stroke] ?? null;
                      const resolvedTime = getSlotTimeMs(athlete, slot, relay.id, manualTimes);
                      const slotManualKey = manualTimeKey(relay.id, slot.key);
                      return (
                        <div key={slot.key} onDragOver={(event) => { if (!isFixed) event.preventDefault(); }} onDrop={(event) => { if (!isFixed) handleDrop(event, relay.id, slot.key); }} className={`min-h-0 rounded-xl border-2 border-dashed p-2 transition sm:min-h-36 sm:p-3 ${isFixed ? 'border-blue-100 bg-blue-50/40' : 'border-slate-200 bg-slate-50 hover:border-blue-300 hover:bg-blue-50/50'}`}>
                          <div className="mb-1 flex items-center justify-between sm:mb-2">
                            <p className="text-xs font-semibold text-slate-700 sm:text-sm">{slot.label}</p>
                            {athlete && !isFixed && <button type="button" onClick={() => clearLeg(relay.id, slot.key)} className="text-xs font-medium text-slate-400 hover:text-red-600">Quitar</button>}
                          </div>

                          {!isFixed && <select
                            value={athleteId ?? ''}
                            onChange={(event) => setSlotAssignment(relay.id, slot.key, event.target.value || null)}
                            disabled={isFixed}
                            className="mb-2 w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-700 sm:mb-3 sm:py-2 sm:text-sm"
                          >
                            <option value="">Seleccionar atleta...</option>
                            {genderEligibleAthletes.map((optionAthlete) => {
                              const assignedElsewhere = isAssignedElsewhere(optionAthlete.id, relay.id, slot.key);
                              const unavailable = unavailableAthleteIds.has(optionAthlete.id);
                              return (
                                <option key={optionAthlete.id} value={optionAthlete.id} className={assignedElsewhere || unavailable ? 'bg-red-50 text-red-700' : undefined}>
                                  {relayOptionLabel(optionAthlete, slot, assignedElsewhere, unavailable)}
                                </option>
                              );
                            })}
                          </select>}

                          {athlete ? (
                            <AthleteCard
                              athlete={athlete}
                              unavailable={unavailableAthleteIds.has(athlete.id)}
                              assignedElsewhere={isAssignedElsewhere(athlete.id, relay.id, slot.key)}
                              dragPayload={isFixed ? undefined : { athleteId: athlete.id, sourceRelayId: relay.id, sourceSlotKey: slot.key }}
                              consideredStroke={slot.stroke}
                              consideredTimeText={formatTime(resolvedTime.ms) ?? rawTime?.text ?? null}
                              consideredTimeSource={resolvedTime.source}
                              consideredTimeInput={rawTime?.ms === null ? (
                                <input
                                  value={manualTimes[slotManualKey] ?? ''}
                                  onChange={(event) => setManualTimes((current) => ({ ...current, [slotManualKey]: event.target.value }))}
                                  placeholder="Tiempo manual ej. 00:35.20"
                                  hidden={isFixed}
                                  className="mt-2 w-full rounded-lg border border-amber-200 bg-white px-2 py-2 text-xs font-normal text-slate-700 outline-none focus:border-amber-400 focus:ring-2 focus:ring-amber-200"
                                />
                              ) : null}
                            />
                          ) : <div className="flex h-24 items-center justify-center rounded-lg border border-slate-200 bg-white text-center text-sm text-slate-400">Seleccione o arrastre a un atleta</div>}

                          {athlete && resolvedTime.ms === null && <p className="mt-2 text-xs font-medium text-amber-600">Sin marca para {slot.stroke_label}; ingrese un tiempo manual si corresponde.</p>}
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
