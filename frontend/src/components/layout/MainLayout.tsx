import React from 'react';
import { Outlet, NavLink } from 'react-router-dom';

export const MainLayout: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-900 flex flex-col">
      {/* Header Premium con gradiente sutil y blur */}
      <header className="sticky top-0 z-50 w-full backdrop-blur-md bg-white/80 border-b border-slate-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <NavLink to="/" className="flex items-center gap-2">
              <img
                src="/web-app-manifest-192x192.png"
                alt="SwimStats Chile"
                className="h-8 w-8"
              />
              <span className="font-bold text-xl tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-slate-900 to-slate-600">
                SwimStats Chile
              </span>
            </NavLink>
            
            {/* Navegación Principal */}
            <nav className="hidden md:flex space-x-1">
              {[
                { name: 'Atletas', path: '/' },
                { name: 'Clubes', path: '/clubs' },
                { name: 'Calendario', path: '/calendar' },
                { name: 'Resultados', path: '/competitions' },
                { name: 'Relevos', path: '/relays' },
              ].map((item) => (
                <NavLink
                  key={item.name}
                  to={item.path}
                  className={({ isActive }) =>
                    `px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 ease-in-out ${
                      isActive
                        ? 'bg-blue-50 text-blue-700 shadow-sm ring-1 ring-blue-700/10'
                        : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                    }`
                  }
                >
                  {item.name}
                </NavLink>
              ))}
            </nav>
          </div>
        </div>
      </header>

      {/* Contenido Principal */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
          <Outlet />
        </div>
      </main>

      {/* Footer Minimalista */}
      <footer className="w-full border-t border-slate-200 bg-white py-6 mt-auto pb-24 md:pb-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className='flex flex-col items-center justify-between gap-2 text-center text-sm text-slate-500 md:flex-row md:text-left'>
            <p>
              &copy; {new Date().getFullYear()} SwimStats Chile. Plataforma de Datos No Oficial.
            </p>
            <p>
              Proyecto desarrollado por{" "}
              <a
                href="https://asaygom.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-slate-700 underline underline-offset-4 hover:text-blue-700"
              >
                Alexis Sayago
              </a>
            </p>
          </div>
        </div>
      </footer>

      {/* Navegación Móvil (Bottom Tab Bar) */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-white/90 backdrop-blur-md border-t border-slate-200 pb-safe">
        <div className="flex justify-around items-center h-16 px-2">
          <NavLink
            to="/"
            className={({ isActive }) =>
              `flex flex-col items-center justify-center w-full h-full space-y-1 ${
                isActive ? 'text-blue-600' : 'text-slate-500 hover:bg-slate-50'
              }`
            }
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <span className="text-[10px] font-medium">Atletas</span>
          </NavLink>

          <NavLink
            to="/clubs"
            className={({ isActive }) =>
              `flex flex-col items-center justify-center w-full h-full space-y-1 ${
                isActive ? 'text-blue-600' : 'text-slate-500 hover:bg-slate-50'
              }`
            }
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            <span className="text-[10px] font-medium">Clubes</span>
          </NavLink>

          <NavLink
            to="/calendar"
            className={({ isActive }) =>
              `flex flex-col items-center justify-center w-full h-full space-y-1 ${
                isActive ? 'text-blue-600' : 'text-slate-500 hover:bg-slate-50'
              }`
            }
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span className="text-[10px] font-medium">Calendario</span>
          </NavLink>

          <NavLink
            to="/competitions"
            className={({ isActive }) =>
              `flex flex-col items-center justify-center w-full h-full space-y-1 ${
                isActive ? 'text-blue-600' : 'text-slate-500 hover:bg-slate-50'
              }`
            }
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
            </svg>
            <span className="text-[10px] font-medium">Resultados</span>
          </NavLink>

          <NavLink
            to="/relays"
            className={({ isActive }) =>
              `flex flex-col items-center justify-center w-full h-full space-y-1 ${
                isActive ? 'text-blue-600' : 'text-slate-500 hover:bg-slate-50'
              }`
            }
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-3-3h-2M7 20H2v-2a3 3 0 013-3h2m10 5v-2a3 3 0 00-3-3h-4a3 3 0 00-3 3v2m10-10a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span className="text-[10px] font-medium">Relevos</span>
          </NavLink>
        </div>
      </nav>
    </div>
  );
};
