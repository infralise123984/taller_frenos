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

  function soloLetrasYNumeros(texto) {
    return texto.replace(/[^0-9a-z]/gi, "");
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
    var patente = campo.value;
    if (soloLetrasYNumeros(patente).length < LARGO_MINIMO) {
      ocultar();
      return;
    }

    // Una consulta por vez: si la operadora sigue escribiendo, la anterior ya
    // no interesa y su respuesta no debe pisar a la nueva.
    if (consulta) {
      consulta.abort();
    }
    consulta = new AbortController();

    var direccion = URL_ESTADO + "?patente=" + encodeURIComponent(patente);
    fetch(direccion, { signal: consulta.signal, headers: { Accept: "application/json" } })
      .then(function (respuesta) {
        return respuesta.ok ? respuesta.json() : Promise.reject(new Error(respuesta.status));
      })
      .then(function (info) {
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

  function rellenar(nombre, valor) {
    if (!valor) {
      return;
    }
    var entrada = document.querySelector('[name="' + nombre + '"]');
    if (entrada) {
      entrada.value = valor;
    }
  }

  contenedor.addEventListener("click", function (evento) {
    var boton = evento.target.closest('[data-accion="cargar-dueno"]');
    if (!boton || !registrado) {
      return;
    }

    rellenar("cliente_nombre", registrado.cliente.nombre);
    rellenar("cliente_telefono", registrado.cliente.telefono);
    rellenar("cliente_email", registrado.cliente.email);
  });

  campo.addEventListener("input", consultarConEspera);
  campo.addEventListener("blur", function () {
    clearTimeout(temporizador);
    consultar();
  });

  // Si la patente llegó precargada (por ejemplo desde la búsqueda), el aviso
  // aparece de inmediato sin que nadie tenga que tocar el campo.
  consultar();
})();
