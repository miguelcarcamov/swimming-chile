import React from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../useAuth';
import { accountService } from '../api/accountService';

type ProfileContributionFormProps = {
  targetType: 'athlete' | 'club';
  targetId: string | number;
};

export const ProfileContributionForm: React.FC<ProfileContributionFormProps> = ({ targetType, targetId }) => {
  const { accessToken, user } = useAuth();
  const queryClient = useQueryClient();
  const [message, setMessage] = React.useState('');
  const [sent, setSent] = React.useState(false);

  const mutation = useMutation({
    mutationFn: () => {
      if (!accessToken) throw new Error('Debes iniciar sesión.');
      return accountService.createContribution(accessToken, {
        athlete_id: targetType === 'athlete' ? targetId : undefined,
        club_id: targetType === 'club' ? targetId : undefined,
        contribution_type: targetType === 'athlete' ? 'athlete_profile' : 'club_profile',
        payload: { message },
      });
    },
    onSuccess: () => {
      setSent(true);
      setMessage('');
      queryClient.invalidateQueries({ queryKey: ['account-contributions', user?.id] });
    },
  });

  if (!accessToken) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="font-bold text-slate-900">Aportar información faltante</h2>
      <p className="mt-1 text-sm text-slate-600">
        Tu aporte queda como sugerencia revisable; no modifica datos públicos automáticamente.
      </p>
      <div className="mt-4 space-y-3">
        <textarea
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Ej: falta ciudad, nombre completo, dato histórico o corrección..."
          rows={3}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="button"
          disabled={mutation.isPending || message.trim().length === 0}
          onClick={() => mutation.mutate()}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
        >
          Enviar aporte
        </button>
        {sent && <p className="text-sm font-medium text-emerald-700">Aporte enviado para revisión.</p>}
        {mutation.isError && <p className="text-sm font-medium text-red-700">No se pudo enviar el aporte.</p>}
      </div>
    </div>
  );
};

