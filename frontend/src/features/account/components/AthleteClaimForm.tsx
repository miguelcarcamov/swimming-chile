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
  const [evidence, setEvidence] = React.useState('');
  const [clubName, setClubName] = React.useState(currentClubName || '');
  const [sent, setSent] = React.useState(false);

  const mutation = useMutation({
    mutationFn: () => {
      if (!accessToken) throw new Error('Debés iniciar sesión.');
      return accountService.createClaim(accessToken, {
        athlete_id: athleteId,
        evidence_message: evidence,
        declared_club_name: clubName || undefined,
      });
    },
    onSuccess: () => {
      setSent(true);
      setEvidence('');
      queryClient.invalidateQueries({ queryKey: ['account-claims', user?.id] });
    },
  });

  if (!accessToken) {
    return (
      <div className="rounded-xl border border-blue-100 bg-blue-50 p-4">
        <h2 className="font-bold text-blue-900">¿Este perfil es tuyo?</h2>
        <p className="mt-1 text-sm text-blue-800">
          Inicia sesión para solicitar el reclamo. La aprobación es manual para proteger la identidad deportiva.
        </p>
        <Link to="/account" className="mt-3 inline-flex rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700">
          Iniciar sesión
        </Link>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="font-bold text-slate-900">Reclamar este perfil</h2>
      <p className="mt-1 text-sm text-slate-600">
        El reclamo queda pendiente hasta que un administrador o gestor autorizado lo revise.
      </p>
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
          placeholder="Cuentanos cómo podemos verificar que eres esta persona..."
          rows={3}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="button"
          disabled={mutation.isPending || evidence.trim().length === 0}
          onClick={() => mutation.mutate()}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
        >
          Enviar reclamo
        </button>
        {sent && <p className="text-sm font-medium text-emerald-700">Reclamo enviado para revisión.</p>}
        {mutation.isError && <p className="text-sm font-medium text-red-700">No se pudo enviar el reclamo.</p>}
      </div>
    </div>
  );
};

