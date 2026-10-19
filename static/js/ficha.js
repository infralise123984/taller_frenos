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

  // La casilla real que Django usa para borrar una línea ya guardada.
  function casillaBorrar(fila) {
    return fila.querySelector("input[name$='-DELETE']");
  }

  function estaQuitada(fila) {
    var casilla = casillaBorrar(fila);
    return Boolean(casilla && casilla.checked);
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
      var casilla = casillaBorrar(fila);
      if (casilla && casilla.checked) {
        casilla.checked = false;
      }
    });
    actualizarTotal();
  }

  function quitarLinea(fila) {
    var casilla = casillaBorrar(fila);
    if (!casilla) {
      return;
    }

    casilla.checked = true;
    // El CSS ya la esconde; esto lo repite para los navegadores sin :has().
    fila.hidden = true;
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

  contenedor.addEventListener("click", function (evento) {
    var boton = evento.target.closest("[data-quitar-linea]");
    if (!boton) {
      return;
    }

    var fila = boton.closest("[data-fila]");
    if (fila) {
      quitarLinea(fila);
    }
  });

  // La rueda del ratón sobre un campo numérico cambia el monto sin querer
  // cuando se recorre la ficha. Al primer giro se suelta el campo: el valor
  // escrito queda intacto y, desde el giro siguiente, la página scrollea.
  function soltarCampoNumericoAlGirarRueda(evento) {
    var campo = evento.target;
    if (!campo || campo.type !== "number" || document.activeElement !== campo) {
      return;
    }

    evento.preventDefault();
    campo.blur();
  }

  document.addEventListener("wheel", soltarCampoNumericoAlGirarRueda, { passive: false });

  contenedor.addEventListener("input", actualizarTotal);
  contenedor.addEventListener("change", actualizarTotal);

  actualizarTotal();
})();
