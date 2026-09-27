# Sistema para Taller de Frenos

Libreta digital para un taller de frenos: el eje es la **patente del vehículo**,
desde la cual se llega al dueño y a todo su historial de mantenciones.

El alcance y el contexto funcional están en `PROJECT_CONTEXT.md`.

> **Estado actual:** mockup funcional. Login real (contraseña + código por
> correo) y las cinco pantallas principales navegables con datos de ejemplo.
> No hay funcionalidades de escritura más allá del registro de ingresos.

---

## Puesta en marcha

Requiere Python 3.13.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements/dev.txt

copy .env.example .env            # y ajustar valores si hace falta
python manage.py migrate
python manage.py seed_demo        # imprime la contraseña generada
python manage.py runserver
```

Abrir <http://127.0.0.1:8000/>.

En desarrollo el correo se imprime en la consola del servidor, así que el
código temporal de acceso aparece ahí (`EMAIL_BACKEND` = consola).

### Comandos útiles

| Comando | Para qué |
| --- | --- |
| `python manage.py test` | Ejecuta las 94 pruebas |
| `python manage.py seed_demo --reset` | Recrea los datos de ejemplo |
| `ruff check . && ruff format .` | Análisis estático y formato |
| `python manage.py check --deploy` | Revisa la configuración de producción |

---

## Estructura

```
config/
  settings/           base / dev / prod  (prod valida y aborta si algo es inseguro)
  formats/es_CL/      formatos chilenos: miles con punto, fechas en español
  urls.py
apps/
  ui.py               clases de presentación compartidas
  accounts/           usuario propio, login por contraseña y por código
    providers/        puerto OtpProvider + implementaciones local y Supabase
    services/         LoginService, limitadores de tasa, IP del cliente
  workshop/           clientes, vehículos, órdenes de trabajo
    selectors.py      consultas de lectura (sin N+1)
    services/         registro de ingresos
templates/            base + parciales + una plantilla por pantalla
```

---

## Acceso al sistema

Hay dos caminos, ambos terminan creando **una sesión de Django**:

### 1. Correo y contraseña

Se apoya en `django.contrib.auth.authenticate`. Tras
`LOGIN_MAX_FAILED_ATTEMPTS` fallos (5 por defecto) la cuenta y la IP quedan
bloqueadas `LOGIN_LOCKOUT_SECONDS` (15 minutos). El contador se guarda en la
caché configurada.

### 2. Correo y código temporal

Flujo en dos pasos con `action` explícito (`request` / `verify`):

1. Se pide un código para un correo.
2. Se valida el código y, si corresponde, se inicia sesión.

El envío y la validación se delegan a un `OtpProvider`. Hay dos
implementaciones intercambiables mediante `OTP_PROVIDER`:

| Valor | Comportamiento | Uso |
| --- | --- | --- |
| `local` | Django genera, hashea, envía y valida el código | Desarrollo y pruebas |
| `supabase` | Supabase Auth envía y valida; Django emite la sesión | Producción |

**Diseño híbrido:** Supabase actúa solo como proveedor de identidad de segundo
factor. Los usuarios, los roles y las sesiones siguen viviendo en Django, de
modo que el dominio no queda acoplado a un servicio externo. Cambiar de
proveedor implica escribir una clase nueva que implemente `OtpProvider` y
registrarla en `apps/accounts/providers/factory.py`.

### Configurar Supabase

1. Crear un proyecto en Supabase y habilitar el proveedor **Email** con
   *Email OTP* activado.
2. Completar en `.env`:

   ```ini
   OTP_PROVIDER=supabase
   SUPABASE_URL=https://<proyecto>.supabase.co
   SUPABASE_ANON_KEY=<anon key>
   SUPABASE_OTP_CREATE_USER=False
   ```

3. Verificar que los correos del taller existan como usuarios en Supabase
   (con `SUPABASE_OTP_CREATE_USER=False`, que es lo recomendado: Supabase no
   debe crear identidades por su cuenta).

`config/settings/prod.py` aborta el arranque si `OTP_PROVIDER` no es
`supabase` o si faltan las credenciales.

---

## Pantallas

| Ruta | Pantalla |
| --- | --- |
| `/cuenta/ingresar/` | Login con contraseña |
| `/cuenta/ingresar/codigo/` | Login con código por correo |
| `/taller/` | Buscar por patente + últimos ingresos |
| `/taller/vehiculo/<patente>/` | Ficha del vehículo e historial |
| `/taller/cliente/<id>/` | Ficha del cliente y sus vehículos |
| `/taller/ingresos/nuevo/` | Registro rápido de un ingreso |

La interfaz está pensada para usarse de pie en el mesón: campos y botones
grandes, textos legibles y diseño que funciona igual en teléfono, tablet y
escritorio. Tailwind se carga por CDN en esta etapa de maqueta; antes de
publicar conviene compilarlo localmente.

---

## Decisiones de arquitectura

| Decisión | Principio que la justifica |
| --- | --- |
| Vistas solo traducen HTTP; la lógica vive en `selectors` y `services` | SRP |
| `OtpProvider` como abstracción con implementaciones intercambiables | DIP + OCP |
| `LoginService` no conoce HTTP: recibe datos y devuelve el usuario | SRP, testeabilidad con dobles |
| `LoginRequiredMiddleware` global: todo exige sesión salvo excepción explícita | Denegación por defecto |
| Código OTP guardado solo como hash Argon2 | Nunca persistir secretos en claro |
| Errores de dominio con mensajes genéricos; el detalle va a los logs | No filtrar información interna |
| Mismo mensaje para "cuenta inexistente" y "contraseña incorrecta" | Evitar enumeración de usuarios |
| Patente y teléfono se almacenan normalizados | Una sola representación evita duplicados |
| Índices declarados en cada `Meta` para los campos de búsqueda | Rendimiento previsible |
| `select_related` / `prefetch_related` centralizados en selectores | Evitar N+1 |

### Modelo de datos

- **`Cliente`** — dueño de uno o más vehículos; se identifica por teléfono
  normalizado para no duplicar fichas por diferencias de formato.
- **`Vehiculo`** — patente única y normalizada (mayúsculas, sin separadores).
- **`OrdenTrabajo`** — una visita: fecha, kilometraje, observaciones y la
  recomendación de próxima mantención (por km, por fecha, o ambas).
- **`ItemTrabajo`** — cada intervención puntual de la visita, tipificada en
  `TipoTrabajo`. Tipificarla ahora permite responder más adelante preguntas
  como "¿cuántos cambios de pastillas hicimos este mes?".

---

## Seguridad implementada

- Contraseñas con **Argon2** y validadores de robustez (mínimo 10 caracteres).
- Códigos OTP de 6 dígitos generados con `secrets`, hasheados, de un solo uso,
  con expiración (5 min) y máximo de intentos (5).
- Límites de tasa por correo y por IP en el login y en la solicitud de códigos,
  más una espera mínima entre solicitudes.
- Cierre de sesión solo por POST.
- Validación de `next` contra redirecciones abiertas.
- Cabeceras `X-Frame-Options: DENY` y `X-Content-Type-Options: nosniff`.
- En producción: HTTPS obligatorio, cookies `Secure`, HSTS, y arranque
  abortado si `DEBUG` está activo, falta `SECRET_KEY`, se usa SQLite o la
  caché no es compartida.
- Cero secretos en el repositorio: todo llega por variables de entorno.

Pendiente antes de publicar: **restringir `ALLOWED_HOSTS` y
`DJANGO_CSRF_TRUSTED_ORIGINS`**, compilar Tailwind localmente y definir una
**CSP** acorde (la CDN de Tailwind obliga a relajarla).

---

## Pruebas

```bash
python manage.py test
```

94 pruebas. Cubren el proveedor OTP local, el servicio de login (incluidos
bloqueos y ausencia de enumeración de usuarios), las vistas de acceso, la
normalización de patentes y teléfonos, el registro de ingresos y la
localización chilena.

Las pruebas de vistas usan un proveedor de OTP falso, de modo que no dependen de
red ni de credenciales.

GitHub Actions ejecuta estas mismas verificaciones (`ruff check`,
`ruff format --check` y las pruebas) en cada push a `main` y en cada pull
request. El flujo no necesita archivo `.env`: los valores por defecto de
`config/settings/dev.py` bastan para probar.

---

## Decisiones abiertas para la entrevista

1. **Próxima mantención:** hoy la ficha muestra la recomendación de la *última*
   visita. ¿Conviene mostrar la última recomendación registrada, aunque
   provenga de una visita anterior?
2. **Cambio de dueño:** el registro rápido conserva el dueño original del
   vehículo. ¿Se necesita un flujo explícito de transferencia?
3. **Catálogo de trabajos:** ¿la lista de `TipoTrabajo` cubre todos los trabajos
   reales del taller? ¿Se necesita adjuntar repuestos con precio?
4. **Roles:** hoy hay usuarios habilitados o deshabilitados a secas. ¿Se
   requiere distinguir entre recepción y mecánico?
5. **Ubicación del local:** ¿el sistema correrá en un servidor con dominio
   propio, o conviene empaquetarlo para uso en la red local del taller?
6. **Respaldo:** con la información en papel no había respaldo. Conviene
   definir una copia periódica de la base de datos desde el primer día.
