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
  var totalFormulario = document.getElementById("id_lineas-TOTAL_FORMS");
  var formato = new Intl.NumberFormat("es-CL");

  function cantidadDeLineas() {
    return totalFormulario ? parseInt(totalFormulario.value, 10) || 0 : 0;
  }

  function actualizarTotal() {
    var total = 0;

    contenedor.querySelectorAll("[data-fila]").forEach(function (fila) {
      var borrar = fila.querySelector(".borrar-linea");
      if (borrar && borrar.checked) {
        return;
      }

      var precio = fila.querySelector("input[name$='-precio']");
      total += parseInt(precio && precio.value ? precio.value : "0", 10) || 0;
    });

    document.querySelectorAll("[data-total-ficha]").forEach(function (salida) {
      salida.textContent = formato.format(total);
    });
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

  if (botonAgregar) {
    botonAgregar.addEventListener("click", function () {
      agregarLinea(selector ? selector.value : "");
      if (selector) {
        selector.value = "";
        selector.focus();
      }
    });
  }

  contenedor.addEventListener("input", actualizarTotal);
  contenedor.addEventListener("change", actualizarTotal);

  actualizarTotal();
})();
