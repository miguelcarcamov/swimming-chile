import React from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '../useAuth';
import { accountService } from '../api/accountService';

type FavoriteButtonProps = {
  targetType: 'athlete' | 'club';
  targetId: string | number;
};

export const FavoriteButton: React.FC<FavoriteButtonProps> = ({ targetType, targetId }) => {
  const { accessToken, user } = useAuth();
  const queryClient = useQueryClient();

  const favoritesQuery = useQuery({
    queryKey: ['account-favorites', user?.id],
    queryFn: () => accountService.getFavorites(accessToken!),
    enabled: Boolean(accessToken),
  });

  const isFavorite = React.useMemo(() => {
    const favorites = favoritesQuery.data;
    if (!favorites) return false;
    const list = targetType === 'athlete' ? favorites.athletes : favorites.clubs;
    return list.some((item) => String(item.id) === String(targetId));
  }, [favoritesQuery.data, targetId, targetType]);

  const mutation = useMutation({
    mutationFn: () => {
      if (!accessToken) throw new Error('Debes iniciar sesión.');
      if (targetType === 'athlete') {
        return isFavorite
          ? accountService.removeAthleteFavorite(accessToken, targetId)
          : accountService.addAthleteFavorite(accessToken, targetId);
      }

      return isFavorite
        ? accountService.removeClubFavorite(accessToken, targetId)
        : accountService.addClubFavorite(accessToken, targetId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['account-favorites', user?.id] });
    },
  });

  if (!accessToken) {
    return (
      <Link
        to="/account"
        className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-100"
      >
        Iniciar sesión para guardar
      </Link>
    );
  }

  return (
    <button
      type="button"
      disabled={mutation.isPending || favoritesQuery.isLoading}
      onClick={() => mutation.mutate()}
      className={`rounded-lg border px-3 py-2 text-sm font-semibold transition-colors disabled:opacity-60 ${
        isFavorite
          ? 'border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100'
          : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
      }`}
    >
      {isFavorite ? '★ Guardado' : '☆ Guardar favorito'}
    </button>
  );
};

