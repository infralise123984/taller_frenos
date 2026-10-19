"""
Constantes de presentación compartidas.

Un único lugar define la "voz visual" del sistema (botones grandes, campos
amplios, alto contraste) porque el mesón del taller se opera de pie, muchas
veces desde una tablet o un teléfono.
"""

from __future__ import annotations


def _campo(*, redondeo: str, relleno: str, tamano: str) -> str:
    """
    Arma la clase de un campo de formulario a partir de sus tres diferencias.

    El tamaño del texto va al final y nunca se repite: si dos clases de tamaño
    conviven en el mismo atributo, gana la que esté después en el CSS compilado
    y el tamaño pedido se pierde en silencio.
    """
    return (
        f"w-full {redondeo} border border-slate-300 bg-white {relleno} {tamano} "
        "text-slate-900 caret-sky-700 shadow-sm placeholder:text-slate-500 "
        "selection:bg-sky-100 selection:text-sky-900 "
        "focus:border-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-200"
    )


# Campos de formulario
INPUT = _campo(redondeo="rounded-xl", relleno="px-4 py-3", tamano="text-lg")
INPUT_COMPACTO = _campo(redondeo="rounded-lg", relleno="px-3 py-2", tamano="text-base")
# Código de seis dígitos de la aplicación autenticadora: grande y espaciado,
# para leerlo de un vistazo en el mesón.
INPUT_CODIGO = _campo(
    redondeo="rounded-xl",
    relleno="px-4 py-3",
    tamano="text-center text-3xl font-semibold tracking-[0.4em]",
)
SELECT = f"{INPUT} appearance-none bg-white pr-10"
TEXTAREA = f"{INPUT} min-h-28 resize-y"

# Botones
BOTON_PRIMARIO = (
    "inline-flex w-full items-center justify-center gap-2 rounded-xl bg-sky-700 px-6 py-4 "
    "text-lg font-semibold text-white shadow-sm transition hover:bg-sky-800 "
    "focus:outline-none focus:ring-2 focus:ring-sky-300 focus:ring-offset-2 "
    "disabled:cursor-not-allowed disabled:opacity-60"
)
BOTON_SECUNDARIO = (
    "inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white "
    "px-5 py-3 text-base font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 "
    "focus:outline-none focus:ring-2 focus:ring-slate-300"
)
BOTON_PELIGRO = (
    "inline-flex items-center justify-center gap-2 rounded-xl border border-red-200 bg-white "
    "px-5 py-3 text-base font-medium text-red-700 shadow-sm transition hover:bg-red-50 "
    "focus:outline-none focus:ring-2 focus:ring-red-200"
)
# Acción destructiva pequeña, para repetir en cada fila de una lista.
BOTON_QUITAR = (
    "inline-flex items-center justify-center gap-1.5 rounded-lg border border-red-200 bg-white "
    "px-3 py-2 text-sm font-medium text-red-700 transition hover:border-red-300 hover:bg-red-50 "
    "focus:outline-none focus:ring-2 focus:ring-red-200"
)

# Tarjetas
TARJETA = "rounded-2xl border border-slate-200 bg-white shadow-sm"
TARJETA_TITULO = "border-b border-slate-100 px-5 py-4 text-base font-semibold text-slate-800"
TARJETA_CUERPO = "px-5 py-4"
