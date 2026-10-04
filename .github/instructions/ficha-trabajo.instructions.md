---
description: Reglas de la ficha de trabajo del taller (líneas, precios, total, descuentos, ficha imprimible y datos del taller).
applyTo: "apps/workshop/**,templates/workshop/**,templates/base.html,static/js/**"
---

# Instrucciones: ficha de trabajo con líneas, precios y total

Instrucciones de proyecto para la ficha del taller. Rigen cualquier cambio en
`apps/workshop/`, sus plantillas y sus pruebas, y nacen de la reunión con la
encargada del taller y del boceto hecho en Paint. Lo que todavía no está decidido
vive en la §14; no se inventa por cuenta propia.

Contexto: hoy el sistema registra la visita con su kilometraje y una lista de
trabajos tipificados (`TipoTrabajo`), pero **no registra montos, ni códigos de
repuesto, ni el total**. La ficha de papel del taller (Taller V.M.D.) sí los
tiene, y es la que se entrega al cliente. Este plan digitaliza esa ficha.

---

## 1. Objetivo

Que registrar una visita sea igual de rápido que llenar la ficha de papel: elegir
cada trabajo de un **menú desplegable**, anotar precio, código y detalle libre por
línea, y que el sistema calcule el **total**. Además, poder **entregar la ficha
impresa** al cliente —con los datos del taller (dirección, ciudad y teléfono)— y
**corregir una ficha ya guardada**.

---

## 2. Decisiones confirmadas con la encargada

| Tema | Decisión |
| --- | --- |
| Precios | Precio **manual por línea** (pesos chilenos, entero). El sistema calcula el total sumando las líneas. |
| Código de freno | **Texto libre**: ella escribe el código y la marca del repuesto a mano. Sin catálogo de repuestos. |
| Posición (delantero / trasero) | Va en el **detalle de texto libre** de la línea. No es un campo aparte. |
| Lista del desplegable | Las **15 líneas del papel** del taller, más `Descuento` y `Otro` (ver §4.1). |
| Ficha impresa | **Sí**: vista imprimible para entregar copia al cliente, **con los datos del taller** (dirección, ciudad, teléfono). |
| Corrección posterior | **Sí**: poder editar una ficha guardada (agregar, borrar líneas, cambiar precios). |
| Datos del taller | Se guardan en un **modelo editable desde el sistema** (admin de Django): **dirección, ciudad y teléfono**, sin re-desplegar. El nombre del taller va fijo en la plantilla. |
| Ficha impresa, contenido | **Solo lo que se ve en el papel**: fecha, marca, patente, líneas **usadas** (no las 15 con espacios en blanco), total y observaciones. Sin kilometraje ni próxima mantención. |
| Fichas anteriores | **No hay**: la migración es solo de esquema, sin conversión de datos. |
| Ficha sin líneas | **No se permite**: al menos una línea para guardar. |
| Descuentos | **Sí existen**: se registran como una línea del tipo `Descuento` con **precio negativo**, que resta del total. |
| Precio sugerido | **No** por ahora: el precio siempre se escribe a mano. |

---

## 3. Situación actual y brecha

| Hoy | Falta |
| --- | --- |
| `ItemTrabajo(tipo, descripcion, repuesto)` — [`models.py`](../../apps/workshop/models.py) | Precio, código de repuesto, marca del repuesto, total |
| 15 botones de checkboxes siempre visibles — [`ingreso_form.html`](../../templates/workshop/ingreso_form.html) | Un desplegable que **agrega una línea** a la vez |
| Solo registrar | Editar una ficha guardada |
| Solo pantalla | Ficha imprimible con formato del papel |
| Los datos del taller (dirección, fono) solo existen en el papel | Modelo `DatosTaller` editables e impresos en la ficha |
| `TipoTrabajo` (8 valores: cambio de pastillas, purga, revisión…) | Los 15 nombres exactos del papel |

---

## 4. Diseño de dominio

### 4.1 Nuevo catálogo `TipoItemFicha`

Reemplaza a `TipoTrabajo`. Los `value` son estables (se guardan en la base de
datos); el `label` es el texto del papel.

```python
class TipoItemFicha(models.TextChoices):
    PASTILLAS = "pastillas", "Pastillas"
    RECT_DISCO = "rect_disco", "Rect. Disco"
    PATINES = "patines", "Patines"
    RECT_TAMBORES = "rect_tambores", "Rect. Tambores"
    GOMAS_CILINDROS = "gomas_cilindros", "Gomas Cilindros"
    LIQUIDO = "liquido", "Líquido"
    SEGURO_PASTILLAS = "seguro_pastillas", "Seguro Pastillas"
    REP_BOMBA = "rep_bomba", "Rep. Bomba"
    KIT_BOMBA = "kit_bomba", "Kit Bomba"
    INST_PIOLA = "inst_piola", "Inst. Piola F/Mano"
    FLEXIBLE = "flexible", "Flexible"
    RESORTE_PATIN = "resorte_patin", "Resorte Patín"
    REP_CALIPER = "rep_caliper", "Rep. Caliper"
    REGULACION_TRAS = "regulacion_tras", "Regulación Tras."
    OBRA_MANO = "obra_mano", "Obra de Mano"
    DESCUENTO = "descuento", "Descuento"             # precio negativo, ver §4.2
    OTRO = "otro", "Otro (escribir en el detalle)"   # escape hatch, ver §11
```

### 4.2 `ItemTrabajo` (línea de la ficha)

```python
tipo = models.CharField("trabajo", max_length=32, choices=TipoItemFicha.choices)
detalle = models.CharField("detalle", max_length=250, blank=True)   # ej. "trasero"
codigo_repuesto = models.CharField("código del repuesto", max_length=60, blank=True)
marca_repuesto = models.CharField("marca del repuesto", max_length=60, blank=True)
precio = models.IntegerField(
    "precio",
    default=0,
    validators=[MinValueValidator(-TOPE_PRECIO), MaxValueValidator(TOPE_PRECIO)],
)
```

- Renombres: `descripcion` → `detalle` (mismo campo, nombre alineado al boceto),
  `repuesto` → `codigo_repuesto`.
- Precio en pesos **enteros**, sin decimales (CLP no usa centavos). Es
  `IntegerField` y no `PositiveIntegerField` porque la línea `Descuento` lleva
  precio **negativo**.
- `default=0`: un presupuesto puede dejar líneas todavía sin precio.
- `TOPE_PRECIO` es una constante del módulo (rango simétrico para positivos y
  descuentos), para no aceptar montos absurdos por error de tipeo.

### 4.3 `OrdenTrabajo.total`

Propiedad calculada, **no** columna almacenada: un total guardado puede quedar
desincronizado de sus líneas. Los descuentos restan solos, porque su precio es
negativo. Se calcula en Python y, para los listados, con
`annotate(Sum("items__precio"))` en el selector.

```python
@property
def total(self) -> int:
    return sum(item.precio for item in self.items.all())
```

### 4.4 `DatosTaller` (encabezado de la ficha impresa)

Fila única (singleton) con los datos del taller que salen impresos en la copia
del cliente: **dirección, ciudad y teléfono**. No se relaciona con las órdenes:
la ficha imprime el valor vigente. El nombre del taller (`TALLER V.M.D.`) y el
rubro (`FRENOS · EMBRAGUES`) quedan fijos como título en la plantilla, porque no
cambian.

```python
class DatosTaller(models.Model):
    """Datos del taller que se imprimen en la ficha entregada al cliente."""

    direccion = models.CharField("dirección", max_length=200, blank=True)
    ciudad = models.CharField("ciudad", max_length=80, blank=True)
    telefono = models.CharField("teléfono", max_length=32, blank=True)
    actualizado_el = models.DateTimeField("actualizado el", auto_now=True)

    class Meta:
        verbose_name = "datos del taller"
        verbose_name_plural = "datos del taller"

    # Efecto secundario explícito: fuerza la fila única (pk=1).
    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls) -> DatosTaller:
        """La única fila; si aún no existe, una instancia vacía."""
        return cls.objects.first() or cls()
```

- Sin dependencias nuevas (nada de `django-solo`): el singleton se resuelve con
  `pk=1` fijo y el admin bloquea crear una segunda fila o borrarla.
  `has_delete_permission` en falso evita que la ficha quede sin encabezado.
- Registrado en el admin de Django, que ya exige `is_staff` (denegación por
  defecto). Solo ella y quien tenga permiso pueden editarlo.
- Selector `datos_del_taller()` en [`selectors.py`](../../apps/workshop/selectors.py)
  para que las vistas no consulten el modelo directo.
- `get_solo()` nunca devuelve `None`: la ficha imprimible funciona aunque nadie
  haya configurado los datos todavía (campos vacíos no se imprimen).
- La migración inicial crea la fila con los datos actuales del papel
  (Alameda N° 0779 al llegar a Av. Victoria, Rancagua, fono 225 384 512) para que
  el sistema quede configurado desde el primer arranque.

### 4.5 Migración (solo esquema, sin datos)

No hay fichas históricas que convertir, así que la migración es la que genera
Django sola:

1. `RenameField`: `descripcion` → `detalle`, `repuesto` → `codigo_repuesto`.
   Conserva lo poco que haya en los entornos de desarrollo.
2. `AddField`: `precio` y `marca_repuesto`.
3. `AlterField` de `tipo` con el catálogo nuevo (las `choices` no son una
   restricción de base de datos, así que no mueve datos).

Sin `RunPython` y sin mapeo de valores antiguos. Los datos de demostración se
regeneran con `seed_demo`, que se actualiza al catálogo nuevo (§12).

---

## 5. Formulario con menú desplegable

El boceto reemplaza los 15 checkboxes por: **elegir en un desplegable → agregar
una línea → completar precio / detalle / código**.

### 5.1 Comportamiento

```
[ Trabajo ▾ ]  [ Detalle ]  [ Código ]  [ Marca ]  [ Precio ]     [ Quitar ]
  Pastillas      trasero       23479      Bosch       2.500
  Obra de Mano                                            2.500
  Descuento                                                  -500
  ─────────────────────────────────────────────────────────────────────
  TOTAL                                                            $ 4.500
```

- Un desplegable "Agregar trabajo…" con el catálogo completo (§4.1: las 15 líneas
  del papel más `Descuento` y `Otro`); al elegir una opción, se agrega una fila en
  blanco con ese tipo. La primera fila parte ya visible.
- Cada fila: `tipo` (select), `detalle` (texto), `codigo_repuesto` (texto),
  `marca_repuesto` (texto), `precio` (número, acepta negativos) y botón "Quitar".
- La línea `Descuento` con precio negativo resta del total. El campo acepta el
  signo menos; el resto son montos positivos.
- El total se muestra abajo y se recalcula al escribir un precio.
- Permitir la **misma línea repetida** (dos cambios de pastillas en el mismo auto).
- Sin JavaScript la ficha sigue funcionando: el formset se envía completo y el
  servidor recalcula todo (§7).

### 5.2 Implementación

- `forms.py`: `LineaFichaForm` (fields del §4.2) y `LineaFichaFormSet`
  (`forms.BaseInlineFormSet` o `formset_factory` con `extra=1`,
  `can_delete=True`, `max_num=30`, `min_num=1`, `validate_min=True`).
- `IngresoRapidoForm` deja de tener `trabajos` (MultipleChoiceField) y
  `grouped_trabajos()`; el formset se instancia en la vista y se pasa al template.
  El resto del formulario (vehículo, cliente, visita, próxima mantención) queda
  igual, así la operadora no reaprende nada del flujo que ya usa.
- Template: `templates/workshop/partials/_linea_ficha.html` para la fila, y un
  `<template>` HTML clonado por un JS mínimo (vanilla, sin build step) para
  "Agregar trabajo". Sin framework JS: el proyecto no tiene bundler.
- La vista sigue igual de simple: valida formset + form y delega al servicio.

---

## 6. Edición de una ficha guardada

- Rutas nuevas: `GET /taller/ingresos/<pk>/editar/` y el mismo POST.
- Servicio `ActualizarFichaService` (o `RegistroIngresoService.actualizar`) que,
  en una transacción, reemplaza las líneas: actualiza las existentes, crea las
  nuevas y borra las marcadas. Nada de `bulk_update` con objetos parciales.
- Editar **no** duplica la visita ni cambia la fecha de ingreso por defecto.
- Solo se puede editar desde la ficha del vehículo; enlace "Editar ficha" con
  botón grande.

---

## 7. Servicios de dominio

`TrabajoSolicitado` ([`services/ingresos.py`](../../apps/workshop/services/ingresos.py)) se
extiende para reflejar la línea real:

```python
@dataclass(frozen=True)
class LineaFicha:
    tipo: str
    precio: int = 0
    detalle: str = ""
    codigo_repuesto: str = ""
    marca_repuesto: str = ""
```

- El **total se calcula en el servidor** al leer la ficha; nunca se acepta un
  total enviado desde el navegador.
- El servicio valida que `tipo` pertenezca a `TipoItemFicha` (denegación por
  defecto) y que `precio` esté dentro del rango permitido (negativo solo tiene
  sentido en la línea `Descuento`).
- Se mantiene la inyección actual (`items=ItemTrabajo.objects`) para poder probar
  con dobles, sin tocar la base de datos.

---

## 8. Ficha imprimible

- Ruta: `GET /taller/ingresos/<pk>/imprimir/` → `workshop/ficha_imprimible.html`.
- Reproduce el papel: encabezado del taller, fecha (DÍA / MES / AÑO), `MARCA` y
  `PATENTE` del vehículo, las **líneas usadas** con su precio, `TOTAL` y
  `OBSERVACIONES`. Nada más: **no** se imprimen kilometraje ni la próxima
  mantención, porque no están en el papel.
- Las líneas usadas salen en el orden en que se agregaron, con el detalle al
  costado (ahí va "trasero") y el descuento como una línea más.
- **Encabezado con los datos del taller** (§4.4): título fijo `TALLER V.M.D. ·
  FRENOS · EMBRAGUES` en la plantilla, más dirección, ciudad y teléfono desde el
  modelo. Cada dato se imprime solo si está cargado (`{% if %}`), para que un
  campo vacío no deje líneas sueltas. El teléfono se imprime legible para
  marcarlo desde el papel (ej. `225 384 512`).
- CSS `@media print` para que salga en una hoja, sin navegación ni botones.
- Formato de moneda chileno con `intcomma` y `$` delante, ya usado en
  [`_orden_card.html`](../../templates/workshop/partials/_orden_card.html).

---

## 9. Pruebas

| Archivo | Qué cubre |
| --- | --- |
| `test_registro_ingreso.py` | Línea con precio, código y detalle se guarda tal cual; `total` suma las líneas y **resta el descuento**; servicio rechaza `tipo` fuera del catálogo y precio fuera de rango |
| `test_ficha_formset.py` (nuevo) | Formset válido/inválido, línea repetida permitida, línea sin precio permitida, borrar línea, ficha sin líneas rechazada, descuento mayor que el total rechazado |
| `test_edicion_ficha.py` (nuevo) | Editar agrega, modifica y borra líneas; el total del servidor manda sobre un total falso enviado por POST |
| `test_ficha_imprimible.py` (nuevo) | La vista responde 200, muestra patente, líneas y total; usuario anónimo es redirigido al login (denegación por defecto) |
| `test_datos_taller.py` (nuevo) | `save()` dos veces deja una sola fila; `get_solo()` sin fila devuelve una instancia vacía; la ficha imprimible muestra dirección, ciudad y teléfono |
| `test_views.py` (ampliar) | Regresión de lo que ya funciona (§15): buscar por patente encuentra al cliente que vuelve, la ficha del vehículo muestra su historial y la ficha del cliente sus vehículos, con el ingreso nuevo registrado por formset |

También hay que actualizar las pruebas y el `seed_demo` que hoy usan
`TipoTrabajo` ([`test_views.py`](../../apps/workshop/tests/test_views.py),
[`seed_demo.py`](../../apps/workshop/management/commands/seed_demo.py)).

---

## 10. Validación, seguridad y datos

- **Validación en el servidor**: tipo contra el enum, `precio` entero dentro de
  `±TOPE_PRECIO` (negativo solo en la línea `Descuento`, y **no** en `OTRO`),
  largos máximos, entre 1 y 30 líneas por ficha, y **el total no puede quedar
  negativo**: un descuento mayor que el trabajo se rechaza con un mensaje claro.
- **Total autoritativo del servidor** (nunca del cliente).
- **CSRF** en el POST del formset (Django ya lo exige) y **autorización**: la
  política global `LoginRequiredMiddleware` cubre las vistas nuevas; se agregan a
  la lista de excepciones solo si fuese necesario (no lo es).
- **XSS**: el detalle y el código son texto libre digitado por la operadora; se
  muestran con autoescape de Django, sin `|safe` ni HTML en ningún campo.
- **Integridad**: registrar y editar en `transaction.atomic`; borrar la visita no
  arrastra al vehículo (`PROTECT` ya vigente).
- **Moneda**: pesos chilenos enteros. Sin IVA, sin decimales, sin múltiples
  monedas (el sistema no emite documentos tributarios, ver `PROJECT_CONTEXT.md`).
- **Datos del taller**: largos máximos validados en el modelo; solo un usuario
  con `is_staff` los edita. No se imprimen como HTML (`autoescape`), así que un
  texto con `<` no rompe la ficha.

---

## 11. Riesgos y decisiones abiertas

1. **Posición como texto libre**: rápido de escribir, pero no permite filtrar
   "cuántos cambios delanteros hicimos". Se acepta por ahora; promoverla a campo
   propio después no rompe lo guardado (se migra desde el detalle).
2. **`OTRO`**: mantenerlo es una red de seguridad para trabajos no listados.
   Si la encargada prefiere un catálogo cerrado, se elimina.
3. **Dónde se editan los datos del taller**: resuelto en §4.4 con modelo + admin
   de Django. El admin es feo y técnico; si a la encargada le resulta incómodo,
   el siguiente paso es una pantalla simple "Datos del taller" dentro del propio
   sistema que guarde sobre el mismo modelo (no cambia el dominio).
4. **Reimpresión de una ficha antigua**: la ficha imprime los datos del taller
   vigentes, no los de la fecha de la visita. Es lo razonable para una copia
   reimpresa, pero conviene confirmarlo.
5. **¿La ficha impresa debe ser obligatoria al guardar** (abrir la impresión
   automáticamente) o solo un botón disponible?
6. **Precios históricos**: cada línea guarda su precio; cambiar precios en el
   futuro no altera las fichas antiguas. Confirmar que es lo deseado.
7. **Respaldo**: siguen en pie las decisiones abiertas del README (copia
   periódica de la base de datos).

---

## 12. Orden de implementación

| Fase | Trabajo | Verificación |
| --- | --- | --- |
| 1 | Enum `TipoItemFicha` + campos de `ItemTrabajo` (migración solo de esquema, sin datos) | `python manage.py test apps.workshop.tests.test_registro_ingreso` |
| 2 | `total` (con descuentos) + selector con `Sum` + actualización de `seed_demo` | `python manage.py test apps.workshop.tests.test_registro_ingreso` |
| 3 | Formset y menú desplegable en el ingreso | `python manage.py test apps.workshop.tests.test_ficha_formset` |
| 4 | Edición de ficha guardada | `python manage.py test apps.workshop.tests.test_edicion_ficha` |
| 5 | `DatosTaller` + admin + migración con los datos del taller | `python manage.py test apps.workshop.tests.test_datos_taller` |
| 6 | Ficha imprimible con encabezado, líneas y total | `python manage.py test apps.workshop.tests.test_ficha_imprimible` |
| 7 | Historial con total, admin actualizado (`ItemTrabajo`, `DatosTaller`), README y estáticos | `python manage.py test` (suite completa) + `ruff check` + `ruff format --check` |

Cada fase se cierra con su prueba nueva en verde **y con las pruebas existentes
intactas** (ver §15). Al final: `python manage.py test` completo, `ruff check` y
`ruff format --check` (lo mismo que corre el CI de
[ci.yml](../../.github/workflows/ci.yml)).

---

## 13. Fuera de alcance

- Boleta o factura tributaria, IVA y documentos del SII.
- Inventario/stock de repuestos y control de compras.
- Catálogo central de precios y de repuestos.
- Multi-moneda y decimales.
- Múltiples usuarios con roles (recepción / mecánico).
- Estados de la ficha y control de pagos (presupuesto / pagada): **pendiente de
  definición** en §14.1, no se implementa en esta entrega.

---

## 14. Puntos aún no definidos

### 14.1 Definiciones que faltan (las decide la encargada)

1. **Estado de la ficha (TBD)**: el papel se imprime cuando el cliente paga, o se
   usa como presupuesto antes de hacer el trabajo. Falta definir si la ficha
   necesita un estado (presupuesto / trabajo hecho / pagada) y si la copia
   impresa cambia según eso (por ejemplo, un título "PRESUPUESTO"). No se
   implementa en esta entrega; el modelo se deja abierto para agregarlo después
   sin rehacer nada.
2. **Folio (sin respuesta todavía)**: propuesta: sin folio propio; basta el número
   interno de la visita.
3. **Redondeo del total**: si el taller redondea a la decena o a la centena,
   definir la regla; hoy el total es la suma exacta de las líneas.
4. **Motivo del descuento**: el descuento se anota como línea `Descuento` con
   detalle libre. ¿Basta así, o quiere una etiqueta fija (por ejemplo "cliente
   frecuente")?

Resueltas: impresión con las líneas usadas nada más, sin fichas históricas que
convertir, mínimo una línea por ficha, `Obra de Mano` como precio, descuentos como
línea negativa y sin precio sugerido (§2).

### 14.2 Trabajo pendiente de listar en las fases (no requiere decisión)

1. **Admin desactualizado**: `ItemTrabajoAdmin` usa `repuesto` y `descripcion` en
   `list_display` / `search_fields` ([`admin.py`](../../apps/workshop/admin.py)) y se
   rompe con los renombres del §4.2.
2. **JavaScript y estáticos**: el proyecto no tiene `static/js/`. Hay que crear el
   archivo, cargarlo con `{% static %}` en [`base.html`](../../templates/base.html) y
   verificar que exista antes del `collectstatic` de Render: en producción se usa
   `CompressedManifestStaticFilesStorage`, que falla si el archivo no está.
3. **Línea en pantallas chicas**: cinco campos por fila no caben en un teléfono.
   Falta definir la fila apilada como tarjeta en móvil y en línea en escritorio.
4. **Documentación**: agregar las rutas nuevas (editar, imprimir) a la tabla
   "Pantallas" y `DatosTaller` a "Modelo de datos" del
   [README](../../README.md), y registrar las rutas en
   [`urls.py`](../../apps/workshop/urls.py).
5. **Tope de precio y de líneas**: definir el valor de `TOPE_PRECIO` (constante,
   misma cifra para positivos y descuentos) y el tope de 30 líneas por ficha.
6. **Botón "Imprimir"** en la ficha del vehículo y en el historial, para reimprimir
   una visita pasada sin entrar a editarla.
7. **Sin auditoría**: no hay registro de quién cambió un precio. Si importa, es un
   modelo nuevo y merece su propio plan.

---

## 15. Lo que ya funciona y no se debe romper

El cliente que vuelve se atiende buscando su **patente**. Todo ese circuito queda
igual: el plan solo cambia el bloque de trabajos del formulario de ingreso y
agrega dos pantallas nuevas.

| Funcionalidad actual | Dónde vive | Cómo se cuida |
| --- | --- | --- |
| **Buscar por patente** (parcial o completa, la coincidencia exacta primero) | [`views.buscar`](../../apps/workshop/views.py), [`BuscarPatenteForm`](../../apps/workshop/forms.py), `buscar_vehiculos` en [`selectors.py`](../../apps/workshop/selectors.py) | No se toca. El formset no participa de la búsqueda |
| **Búsqueda desde el celular del taller** con `?patente=` | [`buscar.html`](../../templates/workshop/buscar.html) | Sin cambios de contrato HTTP ni de URL |
| **Ficha del vehículo con historial cronológico** | [`views.vehiculo_detail`](../../apps/workshop/views.py), [`_orden_card.html`](../../templates/workshop/partials/_orden_card.html) | Se mantiene; solo se agrega el **total** de cada visita (fase 7) |
| **Ficha del cliente** con sus vehículos e historial | [`views.cliente_detail`](../../apps/workshop/views.py), `historial_de_cliente` | Sin cambios |
| **Precarga de la patente** al registrar un auto ya conocido (`?patente=`) | [`views.ingreso_create`](../../apps/workshop/views.py) | Se mantiene igual |
| **Reutilizar cliente y vehículo** en vez de duplicarlos (teléfono y patente normalizados) | `RegistroIngresoService._resolver_cliente` / `_resolver_vehiculo` en [`services/ingresos.py`](../../apps/workshop/services/ingresos.py) | El servicio se extiende, no se reescribe: el auto que ya vino suma una visita nueva |
| **Aviso de ingreso repetido** (misma fecha y kilometraje) | `IngresoDuplicadoError` | Se conserva tal cual |
| **Acceso**: contraseña o código por correo, todo con sesión iniciada | `apps/accounts/` + `LoginRequiredMiddleware` | Las vistas nuevas quedan cubiertas por la misma política |
| **Formatos chilenos** (miles con punto, fechas en español) | `config/formats/es_CL/` | Precios y total usan el mismo formato |
| **94 pruebas actuales** | `apps/workshop/tests/`, `apps/accounts/tests/` | Deben seguir verdes; solo cambian las que hoy usan `TipoTrabajo` |

Regla de trabajo: ninguna fase se cierra con la suite completa en rojo, así el
riesgo de romper la búsqueda por patente se detecta en el momento.
