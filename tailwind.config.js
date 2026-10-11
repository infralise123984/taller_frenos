/*
  Configuración de Tailwind para el sistema del taller.

  El `content` declara dónde buscar clases. Incluye las plantillas, el
  JavaScript y los módulos de Python, porque la "voz visual" del sistema vive en
  `apps/ui.py` y en `apps/workshop/templatetags/ui.py`: si un archivo .py queda
  fuera de esta lista, sus clases no llegan al CSS compilado y la interfaz se ve
  distinta sin que nada avise.

  Las pruebas quedan excluidas a propósito. No dibujan interfaz y, al nombrar las
  clases que verifican, generarían por sí solas utilidades que nadie usa y
  harían pasar esas comprobaciones aunque el origen real dejara de escanearse.

  La versión de Tailwind está fijada en 3.x a propósito, que es la misma que
  servía el CDN, para no cambiar el aspecto del sistema al compilar.
*/
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./apps/**/*.py",
    "!./apps/**/tests/**",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};
