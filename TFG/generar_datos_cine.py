import time
import os
import re
import json
import requests
 
# ── Configuración ──────────────────────────────────────────────────────────────
 
ENDPOINT   = "https://query.wikidata.org/sparql"
HEADERS    = {
    "User-Agent": "MMT_TFG_Bot/1.0 (m.martinezturpin@um.es)",
    "Accept":     "application/sparql-results+json"
}
 
ARCHIVO_DATOS   = "datos_cine_seguro.ttl"
CHECKPOINT_FILE = "checkpoint.txt"
 
PROPIEDADES = "wdt:P57 wdt:P161 wdt:P136 wdt:P577 wdt:P162 wdt:P345 wdt:P495 wdt:P2047 wdt:P364 wdt:P58 wdt:P166 wdt:P2130"
 
PAGINA          = 25    # Películas por página (reducido para evitar truncado de Wikidata)
PAUSA_PAGINA    = 8     # Segundos entre páginas del mismo año
PAUSA_AÑO       = 65   # Segundos entre años (límite de Wikidata)
PAUSA_LABELS    = 2     # Segundos entre bloques de resolución de labels
BLOQUE_LABELS   = 80   # URIs por petición de labels
 
 
# ── Funciones de red ───────────────────────────────────────────────────────────
 
def limpiar_json(texto: str) -> str:
    """
    Elimina caracteres de control inválidos en JSON antes de parsear.
    JSON solo permite \\t \\n \\r sin escapar; el resto (0x00-0x08,
    0x0B, 0x0C, 0x0E-0x1F) son ilegales y causan JSONDecodeError.
    Estos caracteres aparecen en algunos labels de Wikidata.
    """
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', texto)
 
 
def ejecutar_query(query: str, timeout: int = 55) -> list:
    """Lanza una query SPARQL y devuelve los bindings ya saneados."""
    respuesta = requests.get(
        ENDPOINT,
        headers=HEADERS,
        params={"query": query, "format": "json"},
        timeout=timeout
    )
    respuesta.raise_for_status()
    return json.loads(limpiar_json(respuesta.text), strict=False)["results"]["bindings"]
 
 
def ejecutar_con_backoff(query: str, max_intentos: int = 6) -> list:
    """
    Reintenta la query con espera exponencial diferenciando el tipo de error:
    - HTTP 4xx/5xx : problema de red o sobrecarga → esperar y reintentar
    - Timeout      : query demasiado lenta        → esperar y reintentar
    - JSONDecodeError tras saneamiento: respuesta truncada → esperar y reintentar
    """
    for intento in range(max_intentos):
        try:
            return ejecutar_query(query)
 
        except requests.exceptions.HTTPError as e:
            codigo = e.response.status_code
            espera = PAUSA_AÑO * (2 ** intento)
            print(f"  HTTP {codigo} (intento {intento+1}/{max_intentos}). Esperando {espera}s...")
            time.sleep(espera)
 
        except requests.exceptions.Timeout:
            espera = PAUSA_AÑO * (2 ** intento)
            print(f"  Timeout (intento {intento+1}/{max_intentos}). Esperando {espera}s...")
            time.sleep(espera)
 
        except json.JSONDecodeError as e:
            espera = PAUSA_AÑO * (2 ** intento)
            print(f"  JSON inválido tras saneamiento (intento {intento+1}/{max_intentos}): {e}")
            print(f"  Respuesta probablemente truncada. Esperando {espera}s...")
            time.sleep(espera)
 
        except Exception as e:
            espera = PAUSA_AÑO * (2 ** intento)
            print(f"  Error inesperado (intento {intento+1}/{max_intentos}): {e}")
            time.sleep(espera)
 
    raise RuntimeError(f"Query fallida tras {max_intentos} intentos.")
 
 
# ── Lógica de descarga ─────────────────────────────────────────────────────────
 
def obtener_labels(uris: list) -> dict:
    """
    Resuelve los rdfs:label en español de una lista de URIs de Wikidata.
    Trabaja en bloques de BLOQUE_LABELS para no sobrecargar el endpoint.
    """
    labels = {}
    for i in range(0, len(uris), BLOQUE_LABELS):
        bloque = uris[i:i + BLOQUE_LABELS]
        valores = " ".join([f"<{uri}>" for uri in bloque])
        query = f"""
        SELECT ?uri ?label WHERE {{
            VALUES ?uri {{ {valores} }}
            ?uri <http://www.w3.org/2000/01/rdf-schema#label> ?label .
            FILTER(LANG(?label) = "es")
        }}
        """
        try:
            filas = ejecutar_con_backoff(query)
            for fila in filas:
                labels[fila["uri"]["value"]] = fila["label"]["value"]
        except Exception as e:
            print(f"  Aviso: no se pudieron resolver {len(bloque)} labels: {e}")
        time.sleep(PAUSA_LABELS)
    return labels
 
 
def obtener_datos_año(año: int) -> list:
    """
    Descarga todas las propiedades de las películas de un año paginando
    de PAGINA en PAGINA para evitar respuestas truncadas por tamaño.
    """
    offset = 0
    todos = []
 
    while True:
        query = f"""
        SELECT DISTINCT ?pelicula ?propiedad ?valor WHERE {{
            {{
                SELECT DISTINCT ?pelicula WHERE {{
                    ?pelicula wdt:P31 wd:Q11424 ;
                              wdt:P57 [] ;
                              wdt:P345 [] ;
                              wdt:P577 ?fecha ;
                              wikibase:sitelinks ?sl .
                    FILTER(?sl >= 10)
                    FILTER(?fecha >= "{año}-01-01T00:00:00Z"^^xsd:dateTime
                        && ?fecha < "{año+1}-01-01T00:00:00Z"^^xsd:dateTime)
                }} ORDER BY ?pelicula LIMIT {PAGINA} OFFSET {offset}
            }}
            VALUES ?propiedad {{ {PROPIEDADES} }}
            ?pelicula ?propiedad ?valor .
        }}
        """
        try:
            pagina = ejecutar_con_backoff(query)
        except RuntimeError as e:
            print(f"  Página offset={offset} fallida definitivamente: {e}")
            break
 
        if not pagina:
            break
 
        todos.extend(pagina)
        peliculas_pagina = len({fila["pelicula"]["value"] for fila in pagina})
        print(f"  Página offset={offset}: {peliculas_pagina} películas, {len(pagina)} filas")
 
        # La subquery devuelve exactamente PAGINA películas distintas salvo en la última
        if peliculas_pagina < PAGINA:
            break
 
        offset += PAGINA
        time.sleep(PAUSA_PAGINA)
 
    return todos
 
 
def escribir_tripletas(f, resultados: list, labels: dict) -> tuple[int, int]:
    """
    Escribe las tripletas en el archivo TTL abierto.
    Devuelve (películas_únicas, tripletas_escritas).
    """
    peliculas_escritas = set()
    tripletas = 0
 
    for fila in resultados:
        sujeto    = fila["pelicula"]["value"]
        predicado = fila["propiedad"]["value"]
        objeto    = fila["valor"]
 
        # Label e indicador de película solo una vez por entidad
        if sujeto not in peliculas_escritas:
            f.write(f"<{sujeto}> <http://www.wikidata.org/prop/direct/P31> <http://www.wikidata.org/entity/Q11424> .\n")
            if sujeto in labels:
                label = labels[sujeto].replace('"', '\\"').replace('\n', ' ')
                f.write(f'<{sujeto}> <http://www.w3.org/2000/01/rdf-schema#label> "{label}"@es .\n')
            peliculas_escritas.add(sujeto)
 
        if objeto["type"] == "uri":
            obj_uri = objeto["value"]
            f.write(f"<{sujeto}> <{predicado}> <{obj_uri}> .\n")
            if obj_uri in labels:
                label = labels[obj_uri].replace('"', '\\"').replace('\n', ' ')
                f.write(f'<{obj_uri}> <http://www.w3.org/2000/01/rdf-schema#label> "{label}"@es .\n')
        else:
            valor_limpio = objeto["value"].replace('"', '\\"').replace('\n', ' ')
            f.write(f'<{sujeto}> <{predicado}> "{valor_limpio}" .\n')
 
        tripletas += 1
 
    return len(peliculas_escritas), tripletas
 
 
# ── Bucle principal ────────────────────────────────────────────────────────────
 
año_actual = 2026
if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, "r") as f:
        try:
            año_actual = int(f.read().strip())
        except ValueError:
            año_actual = 2026
 
total_tripletas = 0
 
print("Iniciando extracción masiva de películas por año...")
if año_actual < 2026:
    print(f"Resumiendo desde el año guardado: {año_actual}")
 
with open(ARCHIVO_DATOS, "a", encoding="utf-8") as f:
 
    while año_actual >= 1997:
        print(f"\nAño {año_actual}...")
 
        # 1. Datos crudos paginados (sin labels para aligerar la query)
        resultados = obtener_datos_año(año_actual)
 
        if not resultados:
            print(f"  Sin resultados para {año_actual}.")
        else:
            # 2. Resolver labels de todas las URIs que aparecen
            uris = set()
            for fila in resultados:
                uris.add(fila["pelicula"]["value"])
                if fila["valor"]["type"] == "uri":
                    uris.add(fila["valor"]["value"])
            labels = obtener_labels(list(uris))
 
            # 3. Escribir tripletas
            peliculas, tripletas = escribir_tripletas(f, resultados, labels)
            f.flush()
            os.fsync(f.fileno())
 
            total_tripletas += tripletas
            print(f"  {peliculas} películas, {tripletas} tripletas. Total sesión: {total_tripletas}")
 
        # Guardar checkpoint y esperar antes del siguiente año
        año_actual -= 1
        with open(CHECKPOINT_FILE, "w") as cp:
            cp.write(str(año_actual))
 
        print(f"  Esperando {PAUSA_AÑO}s...")
        time.sleep(PAUSA_AÑO)
 
print(f"\nProceso terminado. {total_tripletas} tripletas escritas en '{ARCHIVO_DATOS}'.")
print("Recarga el archivo en Blazegraph para que los nuevos datos estén disponibles.")