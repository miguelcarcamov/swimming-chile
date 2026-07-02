import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Analytics } from '@vercel/analytics/react';
import { RouterProvider } from 'react-router-dom';
import { router } from './app/router';
import { AuthProvider } from './features/account/authContext';

// Configuración global del cliente de React Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false, // En datos estáticos/históricos no necesitamos refrescar al volver a la ventana
      retry: 1, // Reintentos limitados para fallos de red
      staleTime: 5 * 60 * 1000, // Los datos se consideran "frescos" por 5 minutos
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
        <Analytics />
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
