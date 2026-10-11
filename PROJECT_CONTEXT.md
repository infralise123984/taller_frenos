# Contexto del Proyecto: Sistema para Taller de Frenos

## 1. El Problema Actual

El sistema nace para resolver una necesidad operativa real en un taller mecánico independiente especializado en sistemas de frenos. Actualmente, toda la gestión de información se realiza de forma manual en cuadernos y hojas de papel.

Este método tradicional genera varios problemas en el día a día:
* **Pérdida de tiempo al buscar:** Cuando un cliente regresa al taller, buscar en cuadernos viejos qué trabajo se le hizo anteriormente, qué repuestos se utilizaron o en qué fecha vino es un proceso lento y tedioso.
* **Falta de trazabilidad:** No hay forma rápida de saber si un vehículo atendido hace meses aún cuenta con garantía de mano de obra o si ya le corresponde una revisión preventiva de sus componentes de freno.
* **Riesgo de pérdida de información:** Los registros en papel se deterioran con el uso en el taller, se pueden extraviar o manchar con grasa o líquidos de freno.

---

## 2. El Usuario y su Entorno de Trabajo

La usuaria principal del sistema es la encargada del taller/recepción:
* **Entorno físico:** El sistema se utilizará principalmente en el mesón de atención del taller, alternando entre un teléfono móvil, una tablet o un computador de escritorio.
* **Tiempo disponible:** Las consultas y registros deben ser inmediatos. No puede perder minutos navegando entre pantallas complejas mientras tiene al cliente esperando en el mesón o el auto sobre el elevador.
* **Perfil de uso:** La interfaz debe ser extremadamente limpia, intuitiva y directa, con botones grandes y textos legibles, evitando tecnicismos innecesarios o sobrecarga visual.

---

## 3. ¿Qué Debe Resolver el Sistema? (Objetivo Principal)

El objetivo central es digitalizar la ficha de los vehículos y sus intervenciones mecánicas, funcionando como una libreta digital inteligente donde el eje central de búsqueda siempre sea la **patente del vehículo**.

El sistema debe permitir:
1. **Búsqueda instantánea por patente:** Al llegar un vehículo, la operadora ingresa las letras/números de la patente y ve de inmediato la ficha del auto, a quién pertenece y todo su historial de visitas anteriores ordenado cronológicamente.
2. **Historial de mantenciones:** Para cada visita debe quedar claro:
   * Cuándo vino.
   * Qué trabajo puntual se le realizó (por ejemplo: cambio de pastillas, rectificado de discos, purga o cambio de líquido de frenos, reparación de cálipers).
   * Cuándo o a qué kilometraje se le recomendó volver para su próxima mantención preventiva.
3. **Ficha de clientes:** Poder registrar opcionalmente el nombre y número de contacto (para llamarlo o enviarle mensajes por WhatsApp cuando el auto esté listo) y ver si tiene más de un vehículo atendido en el taller.
4. **Registro ágil de nuevos ingresos:** Si entra un auto nuevo que no está en el sistema, debe ser muy rápido registrar su patente, marca y orden de trabajo en una sola pasada. Nombre y teléfono del cliente son opcionales; modelo, año, color y kilometraje actual no se solicitan.

---

## 4. Acceso al Sistema

Dado que es una herramienta de uso interno y personal para el taller:
* **Uso exclusivo:** Solo personas autorizadas del taller deben poder ingresar a ver y editar los datos.
* **Acceso protegido:** La operadora inicia sesión con su correo y contraseña. Si olvida la contraseña, debe contactar a la persona administradora para recuperar el acceso.

---

## 5. Qué NO es este Sistema (Límites Iniciales)

Para mantener el proyecto simple, enfocado y útil desde el primer día:
* No es un sistema de facturación ni emisión de boletas tributarias.
* No es una tienda virtual para vender repuestos por internet.
* No es un software de agendamiento público de horas para clientes externos.
* Es una herramienta de gestión interna y consulta ágil para optimizar el trabajo diario del taller.