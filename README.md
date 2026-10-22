# Taller de Frenos

![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Django 5.2](https://img.shields.io/badge/Django-5.2-092E20?logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Tailwind CSS 3.4](https://img.shields.io/badge/Tailwind-3.4-06B6D4?logo=tailwindcss&logoColor=white)
[![CI](https://github.com/infralise123984/taller_frenos/actions/workflows/ci.yml/badge.svg)](https://github.com/infralise123984/taller_frenos/actions/workflows/ci.yml)
![Licencia: todos los derechos reservados](https://img.shields.io/badge/licencia-todos%20los%20derechos%20reservados-lightgrey)

Sistema de gestión para un taller mecánico independiente especializado en frenos.
Reemplaza la libreta de papel por una ficha digital cuyo eje es la **patente del
vehículo**: desde ahí se llega al dueño, a su historial de mantenciones y a la
ficha que se imprime y se entrega al cliente.

Es un proyecto real, pensado para el mesón de atención: registro rápido,
búsqueda instantánea por patente y una interfaz usable de pie en teléfono,
tablet o escritorio.

> **Estado:** operativo. Registra ingresos, consulta el historial por patente,
> corrige fichas, las imprime y administra cuentas con invitación y 2FA.

El alcance funcional y el contexto del negocio están en
[`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md).

---

## El problema

En un taller pequeño la información vive en cuadernos y hojas de papel. Eso
genera tres problemas cotidianos:

- **Buscar es lento.** Cuando el cliente vuelve, hay que revisar cuadernos
  viejos para saber qué se le hizo, con qué repuestos y cuándo.
- **No hay trazabilidad.** Es difícil saber si un trabajo aún tiene garantía o
  si al vehículo le corresponde una mantención preventiva.
- **El papel se pierde.** Se deteriora con grasa, se moja con líquido de frenos
  y no tiene respaldo.

El sistema resuelve eso con una libreta digital centrada en la patente, sin
convertirse en un ERP ni en un sistema de facturación.

---

## Funcionalidades

| Área | Qué hace |
| --- | --- |
| Búsqueda por patente | Encuentra al vehículo, su dueño y su historial en segundos. Mientras se escribe, avisa si el auto ya vino y muestra la última visita. |
| Historial | Cada visita queda ordenada cronológicamente con trabajos, repuestos, kilometraje y la recomendación de próxima mantención. |
| Clientes | Un cliente puede tener varios vehículos. Patente y teléfono se normalizan para evitar fichas duplicadas. |
| Registro de ingresos | Alta rápida de patente, marca, dueño y orden de trabajo en una sola pasada. |
| Ficha de trabajo | Líneas tipificadas con precio, código y marca del repuesto; descuento como línea negativa; total calculado en el servidor. |
| Corrección e impresión | Las fichas guardadas se pueden editar y se imprimen con los datos del taller. |
| Acceso interno | Sin registro público: invitaciones de un solo uso, login por correo, límite de intentos y 2FA TOTP opcional. |
| PWA | Instalable desde el navegador; guarda solo recursos estáticos y nunca datos del taller. |

---

## Stack

| Capa | Tecnología |
| --- | --- |
| Lenguaje | Python 3.13 |
| Backend | Django 5.2 (vistas, formularios y plantillas del lado del servidor) |
| Base de datos | PostgreSQL en producción; SQLite en desarrollo |
| Frontend | Plantillas Django, Tailwind CSS 3.4 compilado y JavaScript sin framework |
| Seguridad | Argon2 para contraseñas, Fernet para semillas TOTP, limitadores de tasa por correo e IP |
| Servidor | Gunicorn + WhiteNoise |
| Calidad | Ruff (lint y formato) y suite de pruebas de Django |
| CI | GitHub Actions (lint, formato, CSS compilado y pruebas) |

La lógica de negocio vive en servicios y selectores; las vistas solo traducen
HTTP. El detalle está en [Decisiones de arquitectura](#decisiones-de-arquitectura)
y [Estructura](#estructura).

---

## Puesta en marcha

Requiere Python 3.13 y Node.js (solo para compilar Tailwind).

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements/dev.txt

npm ci                            # dependencias de Tailwind

copy .env.example .env            # y ajustar valores si hace falta
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abrir <http://127.0.0.1:8000/>.

En desarrollo, los correos de invitación se imprimen en la consola del servidor
(`EMAIL_BACKEND` = consola). Si alguien olvida su contraseña, debe contactar a
la persona administradora para recuperar el acceso.

En teléfonos compatibles, se puede instalar **Taller de Frenos** desde el menú
del navegador usando **Añadir a pantalla de inicio** o **Instalar aplicación**.
La PWA guarda recursos estáticos para acelerar la carga, pero requiere conexión
para abrir pantallas y consultar o modificar fichas; nunca almacena páginas ni
datos del taller en caché.

### Comandos útiles

| Comando | Para qué |
| --- | --- |
| `python manage.py test` | Ejecuta la suite de pruebas |
| `ruff check . && ruff format .` | Análisis estático y formato |
| `npm run build:css` | Recompila el CSS de Tailwind (obligatorio tras cambiar clases) |
| `npm run watch:css` | Recompila el CSS mientras se edita |
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
  accounts/           usuarios, acceso con contraseña e invitaciones
    services/         LoginService, limitadores de tasa, IP del cliente
  workshop/           clientes, vehículos, órdenes de trabajo
    selectors.py      consultas de lectura (sin N+1)
    services/         registro de ingresos y corrección de fichas
    templatetags/     filtros y clases compartidas para las plantillas
templates/            base + parciales + una plantilla por pantalla
static/js/            líneas de la ficha (agregar, quitar y total en vivo)
```

Las reglas de la ficha de trabajo del taller (líneas, precios, total,
descuentos, impresión y datos del taller) viven como instrucciones de proyecto en
[`.github/instructions/ficha-trabajo.instructions.md`](.github/instructions/ficha-trabajo.instructions.md).

---

## Acceso al sistema

### Creación de cuentas

No hay registro público: el sistema es de uso interno, así que el acceso lo
concede alguien que ya está dentro. Únicamente el personal con acceso al panel
(`is_staff`) puede emitir invitaciones, desde la pantalla **Cuentas**.

Esa persona escribe el correo de la nueva cuenta y obtiene un enlace de un solo
uso, válido `INVITACION_TTL_DIAS` días (7 por defecto). El enlace **se muestra
siempre en pantalla**, además de enviarse por correo, y por eso funciona incluso
en el plan gratuito de Render, donde el SMTP está bloqueado: allí el correo no
sale y basta con entregar el enlace por otra vía. La persona lo abre, elige su
contraseña y queda dentro, ya con la sesión iniciada.

Detalles que conviene conocer:

- Las cuentas nuevas entran como **usuarias normales**, sin acceso al panel de
  administración: no lo necesitan para el trabajo del mesón.
- El token no se guarda nunca en claro, solo su hash SHA-256. Sus 32 bytes
  aleatorios no son adivinables por fuerza bruta.
- Emitir una invitación nueva para el mismo correo **anula la anterior**.
- Si el correo ya tiene cuenta, la invitación se rechaza en el formulario.

### Entrar al sistema

El único método de acceso es correo y contraseña; tras autenticar, Django crea
una sesión. Si una persona olvida su contraseña, debe pedir ayuda a la persona
administradora del sistema.

El login limita intentos fallidos por correo e IP:
`LOGIN_MAX_FAILED_ATTEMPTS` (5 por defecto) bloquea temporalmente durante
`LOGIN_LOCKOUT_SECONDS` (15 minutos). El desafío TOTP y las operaciones de
activación/desactivación comparten ese límite. Los contadores se guardan en la
caché configurada. Al quedar bloqueado, la pantalla dice la hora exacta en que
se puede volver a intentar, porque no hay recuperación automática de contraseña.

Cada usuario puede activar 2FA desde **Seguridad** escaneando un QR con una
aplicación autenticadora. Para iniciar o terminar la configuración se pide la
contraseña actual y un código vigente. El código que confirma la activación no
se marca como consumido para el login: como sigue vigente unos segundos, la
persona puede usarlo para entrar una vez; a partir de ese primer ingreso rige el
bloqueo por reutilización. El desafío de dos pasos indica el paso, la cuenta que
se está verificando y el tiempo de vida que le queda, y ofrece volver al ingreso
con contraseña. La semilla se cifra en la base de datos
con `TOTP_ENCRYPTION_KEY`; producción no arranca sin una clave Fernet válida.
Genera una clave con `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
y guárdala como secreto en el entorno de despliegue. Debe mantenerse estable y
respaldarse de forma segura: perderla o cambiarla impide descifrar las semillas
existentes. Si alguien pierde su dispositivo, administración verifica su
identidad y usa la acción **Restablecer 2FA** en la cuenta correspondiente; la
persona puede volver a configurarlo después.

---

## Pantallas

| Ruta | Pantalla |
| --- | --- |
| `/cuenta/ingresar/` | Login con contraseña |
| `/cuenta/seguridad/2fa/` | Configuración de autenticación en dos pasos |
| `/taller/` | Buscar por patente + últimos ingresos |
| `/taller/vehiculo/<patente>/` | Ficha del vehículo e historial |
| `/taller/cliente/<id>/` | Ficha del cliente y sus vehículos |
| `/taller/ingresos/nuevo/` | Registro rápido de un ingreso |
| `/taller/ingresos/<id>/editar/` | Corregir las líneas de una ficha guardada |
| `/taller/ingresos/<id>/imprimir/` | Ficha lista para imprimir y entregar |
| `/taller/datos-taller/` | Dirección, ciudad y teléfono que salen en la ficha (solo personal con acceso al panel) |

La interfaz está pensada para usarse de pie en el mesón: campos y botones
grandes, textos legibles y diseño que funciona igual en teléfono, tablet y
escritorio. Tailwind se compila a `static/css/tailwind.css` (ver
[Hoja de estilos](#hoja-de-estilos)); la página no carga nada desde CDNs.

En el registro de un ingreso, mientras se escribe la patente la pantalla le
pregunta a `/taller/patentes/estado/` si ese auto ya vino. Es un endpoint JSON
interno (exige sesión iniciada, igual que todo el taller): si el vehículo ya
está registrado, aparece una tarjeta con el dueño, cuántas veces ha venido y qué
se le hizo la última vez, con atajos para ver la ficha completa o cargar los
datos del dueño. Evita volver a registrar de cero un auto conocido y duplicar su
ficha de cliente.

---

## Decisiones de arquitectura

| Decisión | Principio que la justifica |
| --- | --- |
| Vistas solo traducen HTTP; la lógica vive en `selectors` y `services` | SRP |
| `LoginService` no conoce HTTP: recibe datos y devuelve el usuario | SRP, testeabilidad con dobles |
| `LoginRequiredMiddleware` global: todo exige sesión salvo excepción explícita | Denegación por defecto |
| Errores de dominio con mensajes genéricos; el detalle va a los logs | No filtrar información interna |
| Mismo mensaje para "cuenta inexistente" y "contraseña incorrecta" | Evitar enumeración de usuarios |
| Patente y teléfono se almacenan normalizados | Una sola representación evita duplicados |
| Índices declarados en cada `Meta` para los campos de búsqueda | Rendimiento previsible |
| `select_related` / `prefetch_related` centralizados en selectores | Evitar N+1 |
| El total de la visita no se guarda: se calcula sumando sus líneas | Un total almacenado puede desincronizarse |
| El total y las reglas de las líneas se validan en el servidor | El navegador no es una fuente confiable |
| Descuento como una línea más, con precio negativo | Una sola forma de restar, sin casos especiales |

### Modelo de datos

- **`Cliente`** — dueño de uno o más vehículos; se identifica por teléfono
  normalizado para no duplicar fichas por diferencias de formato.
- **`Vehiculo`** — patente única y normalizada (mayúsculas, sin separadores).
- **`OrdenTrabajo`** — una visita: fecha, kilometraje histórico opcional, observaciones y la
  recomendación de próxima mantención (por km, por fecha, o ambas). Su `total`
  es la suma de sus líneas.
- **`ItemTrabajo`** — una línea de la ficha: el trabajo tipificado en
  `TipoItemFicha`, su precio en pesos y los datos del repuesto (código y marca)
  con un detalle de texto libre donde va la posición (delantero, trasero). La
  línea `Descuento` se escribe con precio negativo y resta del total.
- **`DatosTaller`** — fila única con dirección, ciudad y teléfono, los datos que
  salen impresos en la ficha que se entrega al cliente. Se editan desde
  `/taller/datos-taller/` (cuentas con acceso al panel) o desde el admin.

Los detalles de la ficha (líneas, precios, total, impresión y corrección) están
como instrucciones de proyecto en
[`.github/instructions/ficha-trabajo.instructions.md`](.github/instructions/ficha-trabajo.instructions.md).

---

## Seguridad implementada

- Contraseñas con **Argon2** y validadores de robustez (mínimo 10 caracteres).
- Límites de tasa por correo y por IP en el login con contraseña.
- 2FA TOTP opcional por cuenta; semilla cifrada con una clave separada, QR sin
  caché, desafío preautenticado de corta duración y rechazo de códigos repetidos.
- Recuperación de 2FA mediante restablecimiento administrativo tras verificar
  identidad; la semilla no se muestra en el panel de administración.
- Cierre de sesión solo por POST.
- Validación de `next` contra redirecciones abiertas.
- Cabeceras `X-Frame-Options: DENY` y `X-Content-Type-Options: nosniff`.
- En producción: HTTPS obligatorio, cookies `Secure`, HSTS, y arranque
  abortado si `DEBUG` está activo, falta `SECRET_KEY`, se usa SQLite o la
  caché no es compartida.
- Cero secretos en el repositorio: todo llega por variables de entorno.

En producción `ALLOWED_HOSTS` no tiene valores por defecto: hay que declararla, o
dejar que se detecte dentro de Render. Queda pendiente definir una **CSP**
estricta.

---

## Hoja de estilos

Tailwind se compila en un archivo propio y se sirve desde el dominio del taller,
así que la interfaz ya no depende de un CDN ni de tener internet.

| Archivo | Papel |
| --- | --- |
| `assets/css/tailwind.src.css` | Entrada que lee Tailwind. No se sirve. |
| `static/css/tailwind.css` | Resultado compilado y minificado. Versionado. Lo carga la página. |
| `static/css/app.css` | Reglas propias del sistema. Se carga después, para poder sobrescribir. |
| `tailwind.config.js` | Declara dónde buscar clases. |

`tailwind.config.js` busca clases en las plantillas, en el JavaScript **y en los
módulos de Python**, porque la "voz visual" del sistema vive en `apps/ui.py` y en
los `simple_tag` de `apps/workshop/templatetags/ui.py`. Si un archivo con clases
queda fuera de esa lista, sus estilos no se generan y la interfaz cambia sin que
nada avise.

**Tras cambiar clases hay que recompilar** (`npm run build:css`) y versionar el
resultado, porque las pruebas y el despliegue no ejecutan Node. Para que ese
paso no se olvide, el CI recompila el CSS y falla si el archivo versionado no
coincide con su fuente.

En Render el build recompila el CSS por su cuenta (`build.sh`), de modo que lo
publicado siempre corresponde al código desplegado.

Tailwind está fijado en 3.x, y no en 4.x, a propósito: la versión 4 renombra
clases que el sistema ya usa (`shadow-sm`, `outline-none`) y cambia el ancho por
defecto de `ring`, así que migrar exige revisar pantalla por pantalla. Mientras
tanto, `npm audit` informa avisos en dependencias internas de compilación
(`braces`, `postcss-selector-parser`); se aceptan porque solo procesan los
archivos del propio repositorio durante el build, nunca datos de terceros, y
porque la única corrección que ofrece npm es saltar a Tailwind 4. Conviene
revisarlo al migrar de versión.

---

## Despliegue en Render

El repositorio ya trae lo que Render necesita. En el dashboard: *New → Web
Service*, apuntando a este repositorio.

| Campo | Valor |
| --- | --- |
| Language | `Python 3` |
| Build Command | `./build.sh` |
| Start Command | `python -m gunicorn config.wsgi:application --bind 0.0.0.0:$PORT` |
| Health Check Path | `/cuenta/ingresar/` |

El `--bind 0.0.0.0:$PORT` es opcional, pero conviene dejarlo. Sin él gunicorn
escucha en `127.0.0.1:8000` y Render tiene que deducir el puerto leyendo los
registros de arranque: suele funcionar —muchos proyectos lo omiten, y la propia
guía de Django de Render no lo incluye— pero cuando la detección falla el
despliegue se rechaza con un error poco claro. Con el `--bind` el servicio
escucha donde Render lo espera (`0.0.0.0`, puerto indicado por `PORT`, que vale
10000 por defecto) y no queda nada que adivinar.

### Base de datos

Crear una instancia **PostgreSQL** y usar su *Internal Database URL* como
`DATABASE_URL`.

### Variables de entorno

Render define `PORT` y `RENDER_EXTERNAL_HOSTNAME` por su cuenta. El hostname se
agrega automáticamente a `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS`, así que no
hay que declararlo.

| Variable | Valor |
| --- | --- |
| `DJANGO_SECRET_KEY` | Botón *Generate* de Render |
| `TOTP_ENCRYPTION_KEY` | Clave Fernet generada y respaldada de forma segura; no rotarla sin plan de migración |
| `DJANGO_DEBUG` | `False` |
| `DATABASE_URL` | *Internal Database URL* de la base PostgreSQL |
| `CACHE_URL` | `dbcache://frenos_cache` |
| `EMAIL_BACKEND` | Backend de correo opcional para enviar invitaciones; el enlace también se muestra en pantalla |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | Datos del proveedor SMTP |
| `DEFAULT_FROM_EMAIL` | Un remitente real, nunca `@localhost` |
| `DJANGO_TIME_ZONE` | `America/Santiago` |
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` (ver abajo) |
| `BOOTSTRAP_ADMIN_EMAIL` | Correo de la primera cuenta administrativa |
| `BOOTSTRAP_ADMIN_PASSWORD` | Contraseña fuerte para la primera cuenta administrativa |

`DJANGO_SETTINGS_MODULE` no hace falta para servir tráfico —`config/wsgi.py` ya
usa los ajustes de producción— pero sí para los comandos que ejecutes en la
pestaña *Shell*: sin esa variable, `manage.py` usaría los ajustes de desarrollo.

Si agregas un dominio propio, súmalo a `DJANGO_ALLOWED_HOSTS` **y** a
`DJANGO_CSRF_TRUSTED_ORIGINS` con esquema (`https://taller.ejemplo.cl`).

### Cuenta inicial

El sistema no crea usuarios en producción, y la primera cuenta es el único caso
que no puede resolverse con una invitación, porque hace falta estar dentro para
invitar.

En un plan **pago**, desde la pestaña *Shell* del servicio:

```bash
python manage.py createsuperuser
```

En un plan **gratuito sin Shell**, configura `BOOTSTRAP_ADMIN_EMAIL` y
`BOOTSTRAP_ADMIN_PASSWORD` como variables secretas antes del primer despliegue.
El build crea el primer superusuario únicamente si todavía no existe ninguno y
valida la contraseña con las reglas de Django. No carga clientes ni visitas.
Retira ambas variables después de crear la cuenta; el comando no cambia cuentas
existentes ni vuelve a crear una si ya hay un superusuario.

### Dos decisiones que simplifican el despliegue

**Caché en la misma base de datos, sin Redis.** Los límites de intentos de
acceso necesitan un almacén compartido entre workers, y `dbcache://` lo consigue
usando la PostgreSQL que ya existe: sin servicio extra, sin costo adicional y
sobrevive a los reinicios. `build.sh` crea la tabla automáticamente. Si el
sistema crece, pasar a Redis es cambiar `CACHE_URL` por `redis://…`.

El correo SMTP es opcional: se usa solo para enviar invitaciones. El enlace de
invitación también se muestra en pantalla, así que puede entregarse por otra vía
si el proveedor de correo no está configurado o Render bloquea SMTP.

### ¿Hace falta una base de datos?

Sí, y no puede ser SQLite. Ahí viven los clientes, vehículos, visitas, usuarios,
sesiones y los contadores de intentos de acceso. El sistema de archivos de un
servicio web de Render es efímero —se borra en cada despliegue, reinicio o
suspensión—, así que un archivo SQLite perdería todo cada vez.

Basta con la base PostgreSQL gratuita de Render, creada desde el mismo panel. Si
necesitas que siga existiendo más de 30 días, hay que pasarla a un plan pago o
usar un PostgreSQL externo (Supabase, Neon) como `DATABASE_URL`.

### Límites del plan gratuito

- El servicio se suspende tras 15 minutos sin tráfico y tarda cerca de un minuto
  en volver. Conviene abrir la URL antes de mostrársela a alguien.
- **La base PostgreSQL gratuita caduca 30 días después de crearla.** Hay 14 días
  de gracia para pasarla a un plan pago; después Render la elimina con todos sus
  datos. Solo se admite una base gratuita por espacio de trabajo, de 1 GB y sin
  respaldos.
- **No hay acceso a Shell**, por eso configura las variables de bootstrap para
  crear la primera cuenta administrativa durante el build.
- No se puede enviar correo por SMTP (puertos 25, 465 y 587 bloqueados).
- Las invitaciones siguen funcionando: el enlace de alta también aparece en
  pantalla para entregarlo manualmente.
- 512 MB de RAM por instancia. No definas `WEB_CONCURRENCY`; el worker único que
  gunicorn usa por defecto es lo adecuado para este tamaño.
- El plan incluye 750 horas de instancia al mes por espacio de trabajo.

### Versionado de Python

Render usa Python 3.14 por defecto para los servicios creados desde febrero de
2026. El archivo `.python-version` fija 3.13, que es la versión con la que se
probó el proyecto y la que usa la CI.

---

## Pruebas

```bash
python manage.py test
```

La suite cubre el servicio y las vistas de acceso (incluidos bloqueos, rechazo
del antiguo endpoint de códigos y ausencia de enumeración de usuarios), la
normalización de patentes y teléfonos, el registro de ingresos, las líneas de la
ficha (precios, descuentos, corrección e impresión) y la localización chilena.

GitHub Actions ejecuta estas mismas verificaciones (`ruff check`,
`ruff format --check` y las pruebas) en cada push a `main`, `desarrollo` y en
cada pull request. El flujo no necesita archivo `.env`: los valores por defecto
de `config/settings/dev.py` bastan para probar.

---

## Preguntas abiertas y próximos pasos

1. **Próxima mantención:** hoy la ficha muestra la recomendación de la *última*
   visita. ¿Conviene mostrar la última recomendación registrada, aunque
   provenga de una visita anterior?
2. **Cambio de dueño:** el registro rápido conserva el dueño original del
   vehículo. ¿Se necesita un flujo explícito de transferencia?
3. **Catálogo de trabajos:** resuelto en las
   [instrucciones de la ficha de trabajo](.github/instructions/ficha-trabajo.instructions.md):
   la lista son las líneas de la ficha de papel y cada línea lleva precio,
   código y marca del repuesto.
4. **Estado de la ficha:** el papel se imprime al pagar o se usa como
   presupuesto. Falta decidir si la ficha necesita un estado (presupuesto /
   pagada) y si eso cambia la copia impresa. Pendiente de conversar con la
   encargada.
5. **Roles:** hoy hay usuarios habilitados o deshabilitados a secas. ¿Se
   requiere distinguir entre recepción y mecánico?
6. **Ubicación del local:** ¿el sistema correrá en un servidor con dominio
   propio, o conviene empaquetarlo para uso en la red local del taller?
7. **Respaldo:** con la información en papel no había respaldo. Conviene
   definir una copia periódica de la base de datos desde el primer día.
8. **Folio de la ficha:** ¿basta el número interno de la visita, o se necesita
   un folio visible para cuadrar con un correlativo de papel?

---

## Autor

**Tomás Murua Rojas**

- LinkedIn: [tomás murua rojas](https://www.linkedin.com/in/tom%C3%A1s-murua-a03654325/)

---

## Licencia

Este repositorio es **público únicamente como portafolio y muestra técnica**.
El código es propietario y **no** se concede permiso para usarlo, ejecutarlo,
desplegarlo, copiarlo, modificarlo, distribuirlo ni incorporarlo en otro
proyecto. Todos los derechos están reservados.

El aviso legal completo está en [`LICENSE`](LICENSE).

La publicación en GitHub permite ver y bifurcar el repositorio según los
[Términos de Servicio de GitHub](https://docs.github.com/es/site-policy/github-terms/github-terms-of-service);
eso no otorga ningún derecho de uso sobre el software.
