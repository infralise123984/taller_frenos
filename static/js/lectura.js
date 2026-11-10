/*
  Tamaño de letra elegido por la persona que usa el taller.

  La preferencia vive en localStorage y se aplica en <html data-texto="…">,
  que es lo que leen las reglas de static/css/app.css. El script del <head> de
  base.html la aplica antes del primer pintado; este archivo solo conecta los
  botones y mantiene su estado visible.
*/

(function () {
  "use strict";

  var CLAVE = "taller-texto";
  var NIVELES = ["normal", "grande", "muy-grande"];
  var POR_DEFECTO = "grande";

  function nivelGuardado() {
    try {
      var guardado = localStorage.getItem(CLAVE);
      return NIVELES.indexOf(guardado) !== -1 ? guardado : POR_DEFECTO;
    } catch (error) {
      return POR_DEFECTO;
    }
  }

  function marcarActivo(nivel) {
    var botones = document.querySelectorAll("[data-texto-nivel]");
    for (var i = 0; i < botones.length; i += 1) {
      var activo = botones[i].getAttribute("data-texto-nivel") === nivel;
      botones[i].setAttribute("aria-pressed", activo ? "true" : "false");
      botones[i].classList.toggle("bg-sky-700", activo);
      botones[i].classList.toggle("text-white", activo);
      botones[i].classList.toggle("text-slate-700", !activo);
    }
  }

  function aplicar(nivel) {
    document.documentElement.setAttribute("data-texto", nivel);
    marcarActivo(nivel);
    try {
      localStorage.setItem(CLAVE, nivel);
    } catch (error) {
      /* Modo privado sin almacenamiento: el tamaño vale para esta visita. */
    }
  }

  function conectar() {
    var botones = document.querySelectorAll("[data-texto-nivel]");
    for (var i = 0; i < botones.length; i += 1) {
      botones[i].addEventListener("click", function (event) {
        aplicar(event.currentTarget.getAttribute("data-texto-nivel"));
      });
    }
    marcarActivo(document.documentElement.getAttribute("data-texto") || POR_DEFECTO);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", conectar);
  } else {
    conectar();
  }
})();
