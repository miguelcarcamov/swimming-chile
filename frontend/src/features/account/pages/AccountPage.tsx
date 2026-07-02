import React from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../useAuth';
import { accountService } from '../api/accountService';
import { LoadingState } from '../../../components/ui/LoadingState';
import { ErrorState } from '../../../components/ui/ErrorState';
import { EmptyState } from '../../../components/ui/EmptyState';

export const AccountPage: React.FC = () => {
  const { accessToken, isConfigured, isLoading, user, signInWithEmail, signOut } = useAuth();
  const [email, setEmail] = React.useState('');
  const [message, setMessage] = React.useState('');
  const [error, setError] = React.useState('');

  const meQuery = useQuery({
    queryKey: ['account-me', user?.id],
    queryFn: () => accountService.getMe(accessToken!),
    enabled: Boolean(accessToken),
  });

  const favoritesQuery = useQuery({
    queryKey: ['account-favorites', user?.id],
    queryFn: () => accountService.getFavorites(accessToken!),
    enabled: Boolean(accessToken),
  });

  const claimsQuery = useQuery({
    queryKey: ['account-claims', user?.id],
    queryFn: () => accountService.listClaims(accessToken!),
    enabled: Boolean(accessToken),
  });

  const contributionsQuery = useQuery({
    queryKey: ['account-contributions', user?.id],
    queryFn: () => accountService.listContributions(accessToken!),
    enabled: Boolean(accessToken),
  });

  const submitLogin = async (event: React.FormEvent) => {
    event.preventDefault();
    setMessage('');
    setError('');
    try {
      await signInWithEmail(email);
      setMessage('Te enviamos un enlace de acceso al correo.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo iniciar sesión.');
    }
  };

  if (!isConfigured) {
    return (
      <EmptyState
        title="Auth no configurado"
        description="Faltan VITE_SUPABASE_URL y VITE_SUPABASE_ANON_KEY para habilitar cuentas."
      />
    );
  }

  if (isLoading) return <LoadingState />;

  if (!user) {
    return (
      <div className="mx-auto max-w-md rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-bold text-slate-900">Ingresar a SwimStats</h1>
        <p className="mt-2 text-sm text-slate-600">
          Usamos enlace mágico por correo. Sin passwords propios por ahora: menos riesgo, mejor base.
        </p>
        <form onSubmit={submitLogin} className="mt-6 space-y-4">
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="tu@email.cl"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm shadow-sm focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            className="w-full rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-blue-700"
          >
            Enviar enlace de acceso
          </button>
        </form>
        {message && <p className="mt-4 text-sm font-medium text-emerald-700">{message}</p>}
        {error && <p className="mt-4 text-sm font-medium text-red-700">{error}</p>}
      </div>
    );
  }

  if (meQuery.isError) return <ErrorState onRetry={() => meQuery.refetch()} />;

  return (
    <div className="space-y-8">
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Mi cuenta</h1>
            <p className="mt-1 text-sm text-slate-600">{meQuery.data?.email || user.email}</p>
          </div>
          <button
            type="button"
            onClick={() => signOut()}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Cerrar sesión
          </button>
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-xl font-bold text-slate-900">Favoritos</h2>
        {favoritesQuery.isLoading && <LoadingState />}
        {favoritesQuery.data && (
          <div className="grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="font-bold text-slate-900">Atletas</h3>
              {favoritesQuery.data.athletes.length === 0 ? (
                <p className="mt-2 text-sm text-slate-500">Todavía no guardaste atletas.</p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {favoritesQuery.data.athletes.map((athlete) => (
                    <li key={athlete.id}>
                      <Link to={`/athletes/${athlete.id}`} className="font-medium text-blue-700 hover:underline">
                        {athlete.full_name}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="font-bold text-slate-900">Clubes</h3>
              {favoritesQuery.data.clubs.length === 0 ? (
                <p className="mt-2 text-sm text-slate-500">Todavía no guardaste clubes.</p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {favoritesQuery.data.clubs.map((club) => (
                    <li key={club.id}>
                      <Link to={`/clubs/${club.id}`} className="font-medium text-blue-700 hover:underline">
                        {club.name}
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="font-bold text-slate-900">Reclamos de perfil</h2>
          {claimsQuery.data?.data.length ? (
            <ul className="mt-3 space-y-2 text-sm">
              {claimsQuery.data.data.map((claim) => (
                <li key={claim.id} className="flex justify-between gap-3">
                  <span>{claim.athlete_name || `Atleta #${claim.athlete_id}`}</span>
                  <span className="font-semibold text-slate-600">{claim.status}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-slate-500">No hay reclamos enviados.</p>
          )}
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="font-bold text-slate-900">Contribuciones</h2>
          {contributionsQuery.data?.data.length ? (
            <ul className="mt-3 space-y-2 text-sm">
              {contributionsQuery.data.data.map((contribution) => (
                <li key={contribution.id} className="flex justify-between gap-3">
                  <span>{contribution.contribution_type}</span>
                  <span className="font-semibold text-slate-600">{contribution.status}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-slate-500">No hay contribuciones enviadas.</p>
          )}
        </div>
      </section>
    </div>
  );
};

