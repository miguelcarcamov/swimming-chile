import React from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../useAuth';
import { accountService } from '../api/accountService';

type AthleteClaimFormProps = {
  athleteId: string | number;
  currentClubName?: string | null;
};

export const AthleteClaimForm: React.FC<AthleteClaimFormProps> = ({ athleteId, currentClubName }) => {
  const { accessToken, user } = useAuth();
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = React.useState(false);
  const [evidence, setEvidence] = React.useState('');
  const [clubName, setClubName] = React.useState(currentClubName || '');
  const [sent, setSent] = React.useState(false);

  const mutation = useMutation({
    mutationFn: () => {
      if (!accessToken) throw new Error('Debes iniciar sesión.');
      return accountService.createClaim(accessToken, {
        athlete_id: athleteId,
        evidence_message: evidence,
        declared_club_name: clubName || undefined,
      });
    },
    onSuccess: () => {
      setSent(true);
      setIsOpen(false);
      setEvidence('');
      queryClient.invalidateQueries({ queryKey: ['account-claims', user?.id] });
    },
  });

  if (!accessToken) {
    return (
      <div className="rounded-xl border border-blue-100 bg-blue-50 p-4">
        <h2 className="font-bold text-blue-900">¿Este perfil es tuyo?</h2>
        <p className="mt-1 text-sm text-blue-800">
          Inicia sesión para solicitar una revisión manual de identidad.
        </p>
        <Link to="/account" className="mt-3 inline-flex rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700">
          Iniciar sesión
        </Link>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="font-bold text-slate-900">¿Este perfil es tuyo?</h2>
          <p className="mt-1 text-sm text-slate-600">
            Puedes solicitar una revisión manual para vincular tu cuenta con este perfil deportivo.
          </p>
        </div>
        {!isOpen && (
          <button
            type="button"
            onClick={() => {
              setSent(false);
              setIsOpen(true);
            }}
            className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-100"
          >
            Reclamar perfil
          </button>
        )}
      </div>

      {sent && <p className="mt-3 text-sm font-medium text-emerald-700">Reclamo enviado para revisión.</p>}

      {isOpen && (
        <div className="mt-4 space-y-3">
          <input
            value={clubName}
            onChange={(event) => setClubName(event.target.value)}
            placeholder="Club actual o histórico"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:ring-2 focus:ring-blue-500"
          />
          <textarea
            value={evidence}
            onChange={(event) => setEvidence(event.target.value)}
            placeholder="Cuéntanos cómo podemos verificar que eres esta persona..."
            rows={3}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:ring-2 focus:ring-blue-500"
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={mutation.isPending || evidence.trim().length === 0}
              onClick={() => mutation.mutate()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
            >
              Enviar reclamo
            </button>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Cancelar
            </button>
          </div>
          {mutation.isError && <p className="text-sm font-medium text-red-700">No se pudo enviar el reclamo.</p>}
        </div>
      )}
    </div>
  );
};
