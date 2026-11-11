/*
  Aviso de patente ya registrada.

  Mientras la operadora escribe la patente, se le pregunta al servidor si ese
  auto ya vino. Si ya está, aparece una tarjeta con el dueño, sus visitas y la
  última vez que vino, para que no vuelva a registrar de cero un auto conocido
  ni duplique su ficha de cliente.

  Este archivo no arma HTML con datos: clona la tarjeta que vive en la plantilla
  y escribe sobre ella con textContent, para que un nombre con caracteres raros
  nunca se interprete como marcado.

  Si el archivo no carga, no aparece el aviso y nada más se rompe: el servidor
  reutiliza el vehículo y el dueño igual cuando se guarda el ingreso.
*/
(function () {
  "use strict";

  var campo = document.getElementById("id_patente");
  var contenedor = document.querySelector("[data-aviso-patente]");
  var plantilla = document.getElementById("plantilla-aviso-patente");
  if (!campo || !contenedor || !plantilla) {
    return;
  }

  var URL_ESTADO = contenedor.dataset.urlEstado;
  var ESPERA_MS = 350;
  var LARGO_MINIMO = 4;
  var formatoPesos = new Intl.NumberFormat("es-CL");

  var temporizador = null;
  var consulta = null;
  var tarjeta = null;
  var registrado = null;

  // Lo que cargó el atajo "Cargar los datos del dueño" o el propio formulario
  // al abrirse desde la ficha del vehículo, atado a la patente de la que salió:
  // si la patente cambia, esos datos ya no sirven.
  var rellenado = null;

  // Patente cuyos datos ya están escritos en el formulario.
  var patenteCargada = null;

  var CAMPOS_DEL_DUENO = ["cliente_nombre", "cliente_telefono", "cliente_email"];

  // Lo que el formulario trae escrito cuando se abre desde la ficha del auto.
  var CAMPOS_PRECARGADOS = ["marca", ...CAMPOS_DEL_DUENO];

  function soloLetrasYNumeros(texto) {
    return texto.replace(/[^0-9a-z]/gi, "");
  }

  function patenteDelCampo() {
    return soloLetrasYNumeros(campo.value).toUpperCase();
  }

  function abortarConsulta() {
    if (consulta) {
      consulta.abort();
      consulta = null;
    }
  }

  function campoDe(nombre) {
    return tarjeta.querySelector('[data-campo="' + nombre + '"]');
  }

  function escribir(nombre, valor) {
    campoDe(nombre).textContent = valor || "";
  }

  function mostrarBloque(nombre, visible) {
    tarjeta.querySelector('[data-bloque="' + nombre + '"]').hidden = !visible;
  }

  function ocultar() {
    registrado = null;
    tarjeta = null;
    contenedor.replaceChildren();
    contenedor.hidden = true;
  }

  function mostrar(info) {
    registrado = info;

    contenedor.replaceChildren(plantilla.content.cloneNode(true));
    tarjeta = contenedor.firstElementChild;

    escribir("patente", info.patente);
    escribir("descripcion", info.descripcion);
    escribir("total-visitas", String(info.total_visitas));

    var cliente = info.cliente || {};
    var tieneDueno = Boolean(cliente.nombre || cliente.telefono);
    mostrarBloque("dueno", tieneDueno);
    if (tieneDueno) {
      escribir("dueno-nombre", cliente.nombre);
      mostrarBloque("dueno-telefono", Boolean(cliente.telefono));
      escribir("dueno-telefono", cliente.telefono_legible);
    }

    var ultima = info.ultima_visita;
    mostrarBloque("ultima-visita", Boolean(ultima));
    if (ultima) {
      escribir("ultima-fecha", ultima.fecha);
      escribir("ultima-trabajos", ultima.trabajos);
      escribir("ultima-total", "$ " + formatoPesos.format(ultima.total));
    }

    tarjeta.querySelector('[data-accion="ver-ficha"]').href = info.url_ficha;

    var botonDueno = tarjeta.querySelector('[data-accion="cargar-dueno"]');
    botonDueno.hidden = !tieneDueno;

    contenedor.hidden = false;
  }

  function consultar() {
    var patente = patenteDelCampo();

    // El auto y su dueño ya están cargados en el formulario (se llegó desde su
    // ficha): volver a preguntar solo molesta.
    if (patente === patenteCargada) {
      return;
    }

    if (patente.length < LARGO_MINIMO) {
      // Sin patente confiable no hay nada que avisar, y una respuesta que
      // todavía venía en camino ya no corresponde a lo escrito.
      abortarConsulta();
      ocultar();
      return;
    }

    // Una consulta por vez: si la operadora sigue escribiendo, la anterior ya
    // no interesa y su respuesta no debe pisar a la nueva.
    abortarConsulta();
    consulta = new AbortController();

    var direccion = URL_ESTADO + "?patente=" + encodeURIComponent(campo.value);
    fetch(direccion, { signal: consulta.signal, headers: { Accept: "application/json" } })
      .then(function (respuesta) {
        return respuesta.ok ? respuesta.json() : Promise.reject(new Error(respuesta.status));
      })
      .then(function (info) {
        // La patente cambió mientras se esperaba la respuesta: la tarjeta
        // mostraría un auto distinto al que está escrito en el campo.
        if (patenteDelCampo() !== patente) {
          return;
        }

        if (info.registrado) {
          mostrar(info);
        } else {
          ocultar();
        }
      })
      .catch(function () {
        // Si el servidor no responde, se sigue trabajando sin aviso: el ingreso
        // se valida igual al guardar, así que no se molesta a la operadora.
      });
  }

  function consultarConEspera() {
    clearTimeout(temporizador);
    temporizador = setTimeout(consultar, ESPERA_MS);
  }

  function escribirCampo(nombre, valor) {
    var entrada = document.querySelector('[name="' + nombre + '"]');
    if (!entrada) {
      return false;
    }
    entrada.value = valor;
    return true;
  }

  function cargarDatosDelDueno() {
    var cliente = registrado.cliente;
    var valores = {
      cliente_nombre: cliente.nombre || "",
      cliente_telefono: cliente.telefono || "",
      cliente_email: cliente.email || "",
    };

    rellenado = { patente: patenteDelCampo(), valores: {} };

    CAMPOS_DEL_DUENO.forEach(function (nombre) {
      if (!valores[nombre]) {
        return;
      }
      if (escribirCampo(nombre, valores[nombre])) {
        rellenado.valores[nombre] = valores[nombre];
      }
    });

    patenteCargada = rellenado.patente;
  }

  function limpiarDatosPrecargados() {
    if (rellenado) {
      Object.keys(rellenado.valores).forEach(function (nombre) {
        var entrada = document.querySelector('[name="' + nombre + '"]');
        // Solo se borra lo que se cargó y nadie corrigió: lo que la operadora
        // escribió a mano se respeta.
        if (entrada && entrada.value === rellenado.valores[nombre]) {
          entrada.value = "";
        }
      });
    }

    rellenado = null;
    patenteCargada = null;
  }

  // Si el formulario se abrió desde la ficha del vehículo, la patente, la marca
  // y los datos del dueño vienen escritos por el servidor: se recuerdan para
  // poder limpiarlos si la patente cambia.
  function recordarDatosIniciales() {
    var patente = patenteDelCampo();
    if (!patente) {
      return;
    }

    patenteCargada = patente;

    var valores = {};
    CAMPOS_PRECARGADOS.forEach(function (nombre) {
      var entrada = document.querySelector('[name="' + nombre + '"]');
      if (entrada && entrada.value) {
        valores[nombre] = entrada.value;
      }
    });

    if (Object.keys(valores).length) {
      rellenado = { patente: patente, valores: valores };
    }
  }

  contenedor.addEventListener("click", function (evento) {
    var boton = evento.target.closest('[data-accion="cargar-dueno"]');
    if (!boton || !registrado) {
      return;
    }

    cargarDatosDelDueno();
  });

  campo.addEventListener("input", function () {
    // Los datos del dueño pertenecen a la patente de la que se cargaron: con
    // otra patente en el campo se guardarían en el auto equivocado.
    if (patenteCargada && patenteDelCampo() !== patenteCargada) {
      limpiarDatosPrecargados();
    }

    consultarConEspera();
  });

  campo.addEventListener("blur", function () {
    clearTimeout(temporizador);
    consultar();
  });

  // Si la patente llegó escrita desde la ficha del vehículo, sus datos ya vienen
  // en el formulario: no hay nada que preguntar hasta que se escriba otra.
  recordarDatosIniciales();
})();
