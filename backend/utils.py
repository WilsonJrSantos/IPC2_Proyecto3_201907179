import re

def extraer_fecha(texto):
    """ Extrae la primera fecha válida (dd/mm/yyyy) de una cadena. """
    if not texto:
        return "FechaNoValida" # Devolver algo para evitar None
    # Usamos una expresión regular para encontrar el patrón de fecha
    match = re.search(r'\b(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[0-2])/(\d{4})\b', texto)
    return match.group(0) if match else "FechaNoValida" # Devolver algo para evitar None

def validar_nit(nit):
    """ Valida que un NIT tenga el formato correcto. """
    if not nit:
        return False
    # Expresión regular para números, guion y un número o 'K' al final
    return re.fullmatch(r'(\d+-[\dkK])', nit) is not None

