# Registro arqueológico abierto

Mini-proyecto de demostración: API web para registrar **yacimientos**, **unidades estratigráficas (UE)** y
**hallazgos**, con importación desde CSV y salida en JSON/GeoJSON, desplegable con Docker Compose.
Pensado como ejemplo de migración de datos arqueológicos a una plataforma abierta y reutilizable (principios FAIR).

> Los datos de `data/sample/` son **ficticios** y solo sirven de ejemplo.

## Arrancar

```bash
cp .env.example .env        # y cambia la contraseña
docker compose up --build
docker compose exec api python -m app.cli seed    # carga los CSV de ejemplo
```

Documentación interactiva: http://localhost:8000/docs

## Modelo de datos

`Site` (yacimiento) → `Unit` (UE: depósito, corte o estructura) → `Find` (hallazgo).
La tabla `Relation` guarda «la UE superior cubre a la inferior», es decir, las relaciones del diagrama de Harris.

## Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/sites` · `/api/sites.geojson` | Yacimientos en JSON y GeoJSON |
| GET | `/api/sites/{code}/units` | UE de un yacimiento |
| GET | `/api/sites/{code}/matrix` | Matriz estratigráfica por niveles; **409** si hay contradicciones (ciclos) |
| GET | `/api/finds` | Hallazgos con filtros (`site`, `unit`, `category`, `material`, `found_from`, `found_to`) y paginación |
| GET | `/api/export` | Volcado JSON con la licencia de los datos (`DATA_LICENSE`) |
| POST | `/api/import/{sites\|units\|relations\|finds}` | Importa un CSV; `?dry_run=true` valida sin guardar |

## Importación CSV

- Detecta `,` o `;` y las codificaciones UTF-8 y Windows-1252 (Excel en español).
- Acepta decimales con coma en coordenadas.
- Valida cada fila y devuelve un informe con el número de fila de cada error, sin descartar las filas válidas.
- Es idempotente: reimportar el mismo fichero no duplica registros.
- Orden recomendado: `sites` → `units` → `relations` → `finds`.

## Desarrollo y pruebas

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q                                   # SQLite en memoria
TEST_DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/test pytest -q   # PostgreSQL
```

La integración continua (GitHub Actions) ejecuta las pruebas contra PostgreSQL 16.

## Limitaciones

Es una demostración: sin autenticación, sin migraciones (Alembic) y con geometrías de punto únicamente.
