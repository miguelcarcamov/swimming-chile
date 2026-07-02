# Gestión de usuarios: decisión diferida

## Estado

La gestión de usuarios queda documentada como capacidad futura, pero sin
implementación activa por ahora.

## Motivo

En el estado actual de SwimStats Chile, el foco sigue siendo consolidar la
plataforma pública de datos: atletas, clubes, competencias, rankings y calidad
del pipeline. Agregar autenticación, favoritos, reclamos de perfiles y bandejas
de revisión introduce complejidad operativa antes de que exista una necesidad
clara en producto.

La decisión actual es mantener la aplicación pública y sin cuentas de usuario.

## Diseño recomendado cuando se retome

Si la necesidad aparece más adelante, la base conceptual recomendada sigue
siendo:

```text
auth.user_account -> identity.person -> core.athlete_person_link -> core.athlete
                                  \-> club_ops.membership -> core.club
```

Principios:

- `core.athlete` debe seguir siendo una identidad deportiva pública observada
  en resultados.
- Datos civiles o privados, como correos, RUT o fecha de nacimiento civil, no
  deben vivir en `core.athlete`.
- Un reclamo de perfil de atleta debe pasar por revisión manual antes de crear
  o confirmar un vínculo en `core.athlete_person_link`.
- Los aportes de usuarios deben ser sugerencias revisables, no escrituras
  directas sobre datos públicos.
- La autenticación debería delegarse a un proveedor externo al inicio, para no
  operar passwords propios antes de necesitarlo.

## Fuera de alcance actual

- Registro e inicio de sesión.
- Favoritos de atletas o clubes.
- Reclamo de perfiles de atleta.
- Aportes de información desde usuarios autenticados.
- Bandeja administrativa de revisión.
- Integración con Supabase Auth u otro proveedor.

## Nota operativa

La migración `backend/sql/migrations/008_user_profile_interactions.sql` se
mantiene en el repositorio porque ya fue aplicada en bases de datos del proyecto
y funciona como registro de intención/schema histórico. Mantenerla evita romper
la secuencia de migraciones y permite retomar esta capacidad más adelante sin
perder contexto.

Esto no significa que la gestión de usuarios esté activa en la aplicación: no
hay rutas, pantallas ni dependencias runtime para registro, favoritos, reclamos
o aportes de usuarios.
