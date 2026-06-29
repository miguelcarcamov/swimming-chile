# Metodología de UI (Frontend)

Este documento define la forma de trabajar en el código del Frontend para Natación Chile, heredando la disciplina estricta del backend.

## Principios Base

1. **Contract-First**: La interfaz no consume tablas crudas. Todo componente debe consumir un contrato API estable documentado en `api_contracts.md`.
2. **Sin Heurísticas de Negocio en la UI**: El frontend no arregla nombres de atletas ni deduce lógica compleja de torneos; solo renderiza y formatea lo que el backend expone.
3. **Mocks Reproducibles**: Antes de conectar a la base de datos real (FastAPI), toda pantalla debe probarse localmente mediante mocks definidos en `src/test/fixtures/`.
4. **Diseño (Aesthetics)**: Se utiliza **Tailwind CSS v4** para asegurar consistencia, responsividad y una experiencia de usuario fluida y visualmente atractiva sin depender de clases CSS acopladas en archivos separados.

## Flujo de Trabajo para Nuevas Funcionalidades

1. **Diagnóstico y Contrato**:
   - Revisa `api_contracts.md`. Si el endpoint no existe, defínelo primero.
   - Crea/actualiza los esquemas de validación Zod en `src/lib/schemas/`.
2. **Fixture**:
   - Agrega un caso de prueba JSON estático en `src/test/fixtures/` cuando la pantalla dependa de mocks.
3. **Componentes Visuales**:
   - Implementa los componentes requeridos y asegúralos con estados de *Carga* (Loading), *Vacío* (Empty) y *Error*.
4. **Validación Visual**:
   - Prueba el layout de Tailwind localmente.
5. **Cierre**:
   - Evalúa si la funcionalidad cambió contratos API, comportamiento de UI o reglas de presentación; si cambió, actualiza esta documentación o `api_contracts.md`.
   - Asegura que pasen las verificaciones relevantes (`npm run lint` para cambios de UI; pruebas cuando existan o cuando se modifique lógica cubierta por tests).
