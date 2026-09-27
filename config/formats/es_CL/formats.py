"""
Formatos para Chile.

Django no distribuye el locale ``es_CL``, por lo que se declara aquí y se activa
con ``FORMAT_MODULE_PATH``. Sin esto, ``{{ valor|intcomma }}`` y los nombres de
mes caen al inglés (o al español genérico, que usa espacios como separador de
miles) y la lectura en el mesón se vuelve incómoda.

El nombre del paquete debe ser ``es_CL`` en mayúsculas: Django busca el módulo
con ``to_locale(language_code)`` y no normaliza el caso.

Convenciones chilenas: separador de miles con punto, decimales con coma y
semana que comienza el lunes.
"""

DATE_FORMAT = r"j \d\e F \d\e Y"
TIME_FORMAT = "H:i"
DATETIME_FORMAT = r"j \d\e F \d\e Y \a \l\a\s H:i"
YEAR_MONTH_FORMAT = r"F \d\e Y"
MONTH_DAY_FORMAT = r"j \d\e F"
SHORT_DATE_FORMAT = "d/m/Y"
SHORT_DATETIME_FORMAT = "d/m/Y H:i"
FIRST_DAY_OF_WEEK = 1  # lunes

# Los formatos de entrada incluyen ISO 8601 porque los campos
# <input type="date"> del navegador envían siempre "AAAA-MM-DD".
DATE_INPUT_FORMATS = [
    "%Y-%m-%d",  # 2026-09-27 (input type="date")
    "%d/%m/%Y",  # 27/09/2026
    "%d-%m-%Y",  # 27-09-2026
    "%d/%m/%y",  # 27/09/26
]

DATETIME_INPUT_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
]

DECIMAL_SEPARATOR = ","
THOUSAND_SEPARATOR = "."
NUMBER_GROUPING = 3
