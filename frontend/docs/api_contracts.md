# Contratos de API (Frontend -> Backend)

Este documento centraliza los esquemas de comunicación que el frontend espera recibir del backend mediante **FastAPI**. 
La aplicación está construida usando el patrón *Contract-First*, por lo que estos contratos deben respetarse estrictamente para que la UI no rompa.

**Nota sobre IDs:** Todos los `id` en el frontend están tipados como `z.union([z.string(), z.number()])` para soportar tanto los mocks (que usaban UUID) como los IDs reales del backend en PostgreSQL (`BIGSERIAL`).

---

## 1. Atletas (Athletes)

### `GET /api/athletes`
Buscador general de atletas.

**Query Params:**
- `search` (string, opcional): Búsqueda difusa por nombre.

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": 1,
      "full_name": "Soto, Juan",
      "gender": "male",
      "birth_year": 1990,
      "club_name": "Estadio Español",
      "current_club_id": 10,
      "current_club_name": "Estadio Español",
      "current_club_observed_at": "2026-03-28"
    }
  ],
  "meta": { "total_results": 1, "page": 1, "page_size": 20, "total_pages": 1 }
}
```

### `GET /api/athletes/{id}`
Detalle de un atleta, incluyendo sus últimos resultados.

**Response (200 OK):**
```json
{
  "id": 1,
  "full_name": "Soto, Juan",
  "gender": "male",
  "birth_year": 1990,
  "club_name": "Estadio Español",
  "current_club_id": 10,
  "current_club_name": "Estadio Español",
  "current_club_observed_at": "2026-03-28",
  "recent_results": [
    {
      "id": 101,
      "event_name": "50m Libre",
      "stroke": "freestyle",
      "distance_m": 50,
      "course_type": "LCM",
      "competition_name": "Torneo Nacional 2023",
      "competition_date": "2023-11-15T00:00:00Z",
      "result_time_text": "00:25.40",
      "result_time_ms": 25400,
      "status": "valid"
    }
  ]
}
```

---

## 2. Clubes (Clubs)

### `GET /api/clubs`
Listado de clubes afiliados.

**Query Params:**
- Ninguno por ahora.

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": 1,
      "name": "Estadio Español",
      "city": "Santiago",
      "country": "Chile",
      "association_name": "FCHMN"
    }
  ],
  "meta": { "total_results": 1, "page": 1, "page_size": 20, "total_pages": 1 }
}
```

---

## 3. Competencias (Competitions)

### `GET /api/competitions`
Listado de competencias registradas (calendario/histórico).

**Response (200 OK):**
```json
{
  "data": [
    {
      "id": 1,
      "name": "Torneo Nacional FCHMN 2023",
      "date_start": "2023-11-15T00:00:00Z",
      "date_end": "2023-11-17T00:00:00Z",
      "city": "Santiago",
      "country": "Chile",
      "pool_length": 50
    }
  ],
  "meta": { "total_results": 1, "page": 1, "page_size": 20, "total_pages": 1 }
}
```

### `GET /api/competitions/{id}`
Detalle de la competencia, con los resultados anidados por prueba (Eventos).

**Response (200 OK):**
```json
{
  "competition": {
    "id": 1,
    "name": "Torneo Nacional FCHMN 2023",
    "date_start": "2023-11-15T00:00:00Z",
    "city": "Santiago",
    "pool_length": 50
  },
  "events": [
    {
      "id": 1001,
      "distance_m": 50,
      "stroke": "freestyle",
      "gender": "men",
      "age_group": "30-34",
      "results": [
        {
          "rank": 1,
          "athlete_name": "Soto, Juan",
          "athlete_id": 1,
          "club_name": "Estadio Español",
          "time_text": "00:25.40",
          "status": "valid"
        }
      ]
    }
  ]
}
```

---

## 4. Rankings

### `GET /api/rankings`
*(Planificado para el futuro, actualmente no prioritario en UI pero el esquema existe)*

**Response (200 OK):**
```json
{
  "data": [
    {
      "rank": 1,
      "athlete_name": "Soto, Juan",
      "athlete_id": 1,
      "club_name": "Estadio Español",
      "time_text": "00:25.40",
      "time_ms": 25400,
      "competition_name": "Torneo Nacional 2023",
      "date": "2023-11-15T00:00:00Z",
      "distance_m": 50,
      "stroke": "freestyle",
      "course_type": "LCM",
      "gender": "male",
      "age_group": "30-34"
    }
  ],
  "meta": { "total_results": 1, "page": 1, "page_size": 20, "total_pages": 1 }
}
```
