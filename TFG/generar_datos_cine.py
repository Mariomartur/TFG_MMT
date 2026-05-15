import time
import os
from SPARQLWrapper import SPARQLWrapper, JSON

sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
# El JSON es mil veces más robusto que el XML para extraer datos de Wikidata
sparql.setReturnFormat(JSON)

TAMANO_BLOQUE = 500  # Un bloque ligero para que la API responda al instante
total_tripletas = 0

# Archivo de checkpoint para guardar la última URL procesada
CHECKPOINT_FILE = "checkpoint.txt"
ARCHIVO_DATOS = "datos_cine_seguro.ttl"

# Leemos el último checkpoint si existe
offset_actual = 0
if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, "r") as f:
        try:
            offset_actual = int(f.read().strip())
        except ValueError:
            offset_actual = 0

print(f"🎬 Iniciando extracción masiva de películas (A prueba de fallos y resumible)...")
if offset_actual > 0:
    print(f"Resumiendo desde el offset guardado: {offset_actual}")

# Abrimos el archivo en modo "append" ("a") para NO sobreescribir lo de antes
with open(ARCHIVO_DATOS, "a", encoding="utf-8") as f:
    
    while True:
        print(f"\nDescargando bloque de películas (Offset: {offset_actual})...")
        
        # Volvemos a usar OFFSET porque ORDER BY en Wikidata colapsa al intentar ordenar 300,000 películas
        # El Label service es la forma más rápida de obtener los labels
        query = f"""
        SELECT ?pelicula ?propiedad ?valor ?peliculaLabel ?valorLabel WHERE {{
            {{
                SELECT ?pelicula WHERE {{
                    ?pelicula wdt:P31 wd:Q11424 .
                    ?pelicula wdt:P57 ?director .
                    ?pelicula wdt:P345 ?imdb .

                    ?pelicula wikibase:sitelinks ?sitelinks .
                    FILTER(?sitelinks >= 20)
                }}
                LIMIT {TAMANO_BLOQUE}
                OFFSET {offset_actual}
            }}
            VALUES ?propiedad {{ wdt:P57 wdt:P161 wdt:P136 wdt:P577 wdt:P162 wdt:P345 }}
            ?pelicula ?propiedad ?valor .
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "es". }}
        }}
        """

        sparql.setQuery(query)
        
        # Reintentos automáticos
        intentos = 0
        max_intentos = 5
        resultados = None
        
        while intentos < max_intentos:
            try:
                resultados = sparql.query().convert()["results"]["bindings"]
                break
            except Exception as e:
                intentos += 1
                print(f"❌ Error HTTP con Wikidata (Intento {intentos}/{max_intentos}): {e}")
                if intentos == max_intentos:
                    print("Demasiados errores seguidos. Deteniendo el script de forma segura. Vuelve a ejecutarlo más tarde.")
                    exit(1)
                espera = 10 * intentos
                print(f"Esperando {espera} segundos antes de reintentar el mismo bloque...")
                time.sleep(espera)
        
        if len(resultados) == 0:
            print("\n¡Extracción completada! No quedan más películas en Wikidata.")
            break
            
        tripletas_escritas = 0
        
        for fila in resultados:
            sujeto = fila["pelicula"]["value"]
            predicado = fila["propiedad"]["value"]
            objeto_dato = fila["valor"]
            
            # Aseguramos que la película queda clasificada como película (P31 -> Q11424)
            f.write(f"<{sujeto}> <http://www.wikidata.org/prop/direct/P31> <http://www.wikidata.org/entity/Q11424> .\n")
            
            # Escribimos el label del sujeto si existe
            if "peliculaLabel" in fila:
                label_sujeto = fila["peliculaLabel"]["value"].replace('"', '\\"').replace('\n', ' ')
                f.write(f'<{sujeto}> <http://www.w3.org/2000/01/rdf-schema#label> "{label_sujeto}"@es .\n')
            
            # Si el valor es una URL (ej: otro ID de Wikidata)
            if objeto_dato["type"] == "uri":
                f.write(f"<{sujeto}> <{predicado}> <{objeto_dato['value']}> .\n")
                # Escribimos el label del valor si existe
                if "valorLabel" in fila:
                    label_valor = fila["valorLabel"]["value"].replace('"', '\\"').replace('\n', ' ')
                    f.write(f'<{objeto_dato["value"]}> <http://www.w3.org/2000/01/rdf-schema#label> "{label_valor}"@es .\n')
            # Si el valor es texto o número (ej: fecha, ID de IMDb)
            else:
                valor_limpio = objeto_dato["value"].replace('"', '\\"').replace('\n', ' ')
                f.write(f'<{sujeto}> <{predicado}> "{valor_limpio}" .\n')
            
            tripletas_escritas += 1
            
        # Volcar al disco duro instantáneamente para evitar pérdida por apagado de PC
        f.flush()
        os.fsync(f.fileno())
            
        total_tripletas += tripletas_escritas
        print(f"  -> Se guardaron {tripletas_escritas} tripletas. Total en esta sesión: {total_tripletas}")
        
        # Guardar checkpoint para poder resumir si cancelamos
        offset_actual += TAMANO_BLOQUE
        with open(CHECKPOINT_FILE, "w") as cp:
            cp.write(str(offset_actual))
            
        time.sleep(1) # Pequeña pausa de cortesía para Wikidata

print("\n✅ Proceso terminado. Sube el archivo 'datos_cine_seguro.ttl' a Blazegraph.")