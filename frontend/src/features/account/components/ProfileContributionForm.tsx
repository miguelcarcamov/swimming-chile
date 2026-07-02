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
  const [isOpen, setIsOpen] = React.useState(false);
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
      setIsOpen(false);
      setMessage('');
      queryClient.invalidateQueries({ queryKey: ['account-contributions', user?.id] });
    },
  });

  if (!accessToken) return null;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="font-bold text-slate-900">Información faltante o incorrecta</h2>
          <p className="mt-1 text-sm text-slate-600">
            Puedes enviar una sugerencia revisable. No modifica datos públicos automáticamente.
          </p>
        </div>
        {!isOpen && (
          <button
            type="button"
            onClick={() => {
              setSent(false);
              setIsOpen(true);
            }}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Aportar información
          </button>
        )}
      </div>

      {sent && <p className="mt-3 text-sm font-medium text-emerald-700">Aporte enviado para revisión.</p>}

      {isOpen && (
        <div className="mt-4 space-y-3">
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Ej: falta ciudad, nombre completo, dato histórico o corrección..."
            rows={3}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:ring-2 focus:ring-blue-500"
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={mutation.isPending || message.trim().length === 0}
              onClick={() => mutation.mutate()}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
            >
              Enviar aporte
            </button>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Cancelar
            </button>
          </div>
          {mutation.isError && <p className="text-sm font-medium text-red-700">No se pudo enviar el aporte.</p>}
        </div>
      )}
    </div>
  );
};
