import React from 'react';
import { Link } from 'react-router-dom';

const primaryActions = [
  {
    title: 'Resultados por atleta',
    description: 'Encuentra nadadores y revisa su historial competitivo.',
    to: '/athletes',
  },
  {
    title: 'Ver clubes',
    description: 'Explora clubes y asistencia a competencias.',
    to: '/clubs',
  },
  {
    title: 'Resultados por competencia',
    description: 'Consulta competencias y resultados cargados.',
    to: '/competitions',
  },
  {
    title: 'Calendario',
    description: 'Revisa próximas competencias disponibles.',
    to: '/calendar',
  },
];

export const HomePage: React.FC = () => (
  <div className="space-y-10">
    <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
      <div className="grid gap-8 p-6 md:grid-cols-[1.2fr_0.8fr] md:p-10">
        <div className="flex flex-col justify-center">
          <span className="mb-4 inline-flex w-fit rounded-full bg-blue-50 px-3 py-1 text-sm font-semibold text-blue-700 ring-1 ring-blue-700/10">
            Plataforma de datos de natación master
          </span>
          <h1 className="text-4xl font-bold tracking-tight text-slate-950 md:text-5xl">
            SwimStats Chile
          </h1>
          <p className="mt-4 max-w-2xl text-lg leading-8 text-slate-600">
            Explora atletas, clubes, competencias y resultados históricos de natación en Chile desde una interfaz simple y orientada a datos.
          </p>
          <p className="mt-3 max-w-2xl text-sm text-slate-500">
            Proyecto independiente y no oficial. Los datos se construyen desde resultados públicos y procesos de validación propios.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              to="/athletes"
              className="inline-flex items-center justify-center rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-700"
            >
              Ver resultados por atleta
            </Link>
            <Link
              to="/competitions"
              className="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
            >
              Ver resultados por competencia
            </Link>
          </div>
        </div>

        <div className="hidden rounded-2xl bg-gradient-to-br from-blue-50 via-slate-50 to-cyan-50 p-6 ring-1 ring-slate-200 md:block">
          <div className="grid h-full gap-4">
            <div className="rounded-2xl bg-white/80 p-4 shadow-sm">
              <p className="text-sm font-semibold text-slate-900">Datos centralizados</p>
              <p className="mt-1 text-sm text-slate-500">Resultados, atletas y clubes en un solo lugar.</p>
            </div>
            <div className="rounded-2xl bg-white/80 p-4 shadow-sm">
              <p className="text-sm font-semibold text-slate-900">Historial competitivo</p>
              <p className="mt-1 text-sm text-slate-500">Consulta marcas, competencias y evolución.</p>
            </div>
            <div className="rounded-2xl bg-white/80 p-4 shadow-sm">
              <p className="text-sm font-semibold text-slate-900">Exploración por club</p>
              <p className="mt-1 text-sm text-slate-500">Visualiza planteles, asistencia y participación.</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section className="hidden gap-4 md:grid md:grid-cols-4">
      {primaryActions.map(action => (
        <Link
          key={action.to}
          to={action.to}
          className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-md"
        >
          <h2 className="font-bold text-slate-900 group-hover:text-blue-700">{action.title}</h2>
          <p className="mt-2 text-sm leading-6 text-slate-500">{action.description}</p>
        </Link>
      ))}
    </section>
  </div>
);
