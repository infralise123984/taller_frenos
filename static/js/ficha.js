/*
  Líneas de la ficha de trabajo.

  Agrega una línea nueva clonando la plantilla que quedó en el HTML y recalcula
  el total mientras se escribe. Sin este archivo la ficha sigue siendo válida:
  se envía con las líneas que ya venían dibujadas y el servidor vuelve a sumar
  el total por su cuenta.
*/
(function () {
  "use strict";

  var contenedor = document.querySelector("[data-lineas]");
  if (!contenedor) {
    return;
  }

  var plantilla = document.getElementById("plantilla-linea");
  var selector = document.querySelector("[data-selector-trabajo]");
  var botonAgregar = document.querySelector("[data-agregar-linea]");
  var avisoQuitadas = document.querySelector("[data-aviso-quitadas]");
  var botonDeshacer = document.querySelector("[data-deshacer-quitar]");
  var totalFormulario = document.getElementById("id_lineas-TOTAL_FORMS");
  var formato = new Intl.NumberFormat("es-CL");

  function cantidadDeLineas() {
    return totalFormulario ? parseInt(totalFormulario.value, 10) || 0 : 0;
  }

  function filas() {
    return Array.prototype.slice.call(contenedor.querySelectorAll("[data-fila]"));
  }

  function estaQuitada(fila) {
    var borrar = fila.querySelector(".borrar-linea");
    return Boolean(borrar && borrar.checked);
  }

  function actualizarAviso() {
    if (!avisoQuitadas) {
      return;
    }
    var hayQuitadas = filas().some(estaQuitada);
    avisoQuitadas.classList.toggle("hidden", !hayQuitadas);
  }

  function actualizarTotal() {
    var total = 0;

    filas().forEach(function (fila) {
      var quitada = estaQuitada(fila);
      // El CSS ya la esconde; esto lo repite para los navegadores sin :has().
      fila.hidden = quitada;

      if (quitada) {
        return;
      }

      var precio = fila.querySelector("input[name$='-precio']");
      total += parseInt(precio && precio.value ? precio.value : "0", 10) || 0;
    });

    document.querySelectorAll("[data-total-ficha]").forEach(function (salida) {
      salida.textContent = formato.format(total);
    });

    actualizarAviso();
  }

  function agregarLinea(tipo) {
    if (!plantilla || !totalFormulario) {
      return;
    }

    var indice = cantidadDeLineas();
    var html = plantilla.innerHTML.replace(/__prefix__/g, indice);
    var contenedorNuevo = document.createElement("div");
    contenedorNuevo.innerHTML = html.trim();

    var fila = contenedorNuevo.firstElementChild;
    if (!fila) {
      return;
    }

    if (tipo) {
      var seleccion = fila.querySelector("select[name$='-tipo']");
      if (seleccion) {
        seleccion.value = tipo;
      }
    }

    contenedor.appendChild(fila);
    totalFormulario.value = indice + 1;
    actualizarTotal();

    var detalle = fila.querySelector("input[name$='-detalle']");
    if (detalle) {
      detalle.focus();
    }
  }

  function deshacerQuitadas() {
    filas().forEach(function (fila) {
      var borrar = fila.querySelector(".borrar-linea");
      if (borrar && borrar.checked) {
        borrar.checked = false;
      }
    });
    actualizarTotal();
  }

  if (botonAgregar) {
    botonAgregar.addEventListener("click", function () {
      agregarLinea(selector ? selector.value : "");
      if (selector) {
        selector.value = "";
        selector.focus();
      }
    });
  }

  if (botonDeshacer) {
    botonDeshacer.addEventListener("click", deshacerQuitadas);
  }

  contenedor.addEventListener("input", actualizarTotal);
  contenedor.addEventListener("change", actualizarTotal);

  actualizarTotal();
})();
