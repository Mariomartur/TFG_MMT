import time
import os
from SPARQLWrapper import SPARQLWrapper, JSON

sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
sparql.addCustomHttpHeader("User-Agent", "MMT_TFG_Bot/1.0 (m.martinezturpin@um.es)")
sparql.setReturnFormat(JSON)

TAMANO_BLOQUE = 500 
total_tripletas = 0

CHECKPOINT_FILE = "checkpoint.txt"
ARCHIVO_DATOS = "datos_cine_seguro.ttl"

offset_actual = 0
if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, "r") as f:
        try:
            offset_actual = int(f.read().strip())
        except ValueError:
            offset_actual = 0

print(f"🎬 Iniciando extracción masiva de películas...")
if offset_actual > 0:
    print(f"Resumiendo desde el offset guardado: {offset_actual}")

with open(ARCHIVO_DATOS, "a", encoding="utf-8") as f:
    
    while True:
        print(f"\nDescargando bloque de películas (Offset: {offset_actual})...")
        
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
                ORDER BY ?pelicula
                LIMIT {TAMANO_BLOQUE}
                OFFSET {offset_actual}
            }}
            VALUES ?propiedad {{ wdt:P57 wdt:P161 wdt:P136 wdt:P577 wdt:P162 wdt:P345 }}
            ?pelicula ?propiedad ?valor .
            SERVICE wikibase:label {{ bd:serviceParam wikibase:language "es". }}
        }}
        """

        sparql.setQuery(query)
        
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
            
            f.write(f"<{sujeto}> <http://www.wikidata.org/prop/direct/P31> <http://www.wikidata.org/entity/Q11424> .\n")
            
            if "peliculaLabel" in fila:
                label_sujeto = fila["peliculaLabel"]["value"].replace('"', '\\"').replace('\n', ' ')
                f.write(f'<{sujeto}> <http://www.w3.org/2000/01/rdf-schema#label> "{label_sujeto}"@es .\n')
            
            if objeto_dato["type"] == "uri":
                f.write(f"<{sujeto}> <{predicado}> <{objeto_dato['value']}> .\n")
                if "valorLabel" in fila:
                    label_valor = fila["valorLabel"]["value"].replace('"', '\\"').replace('\n', ' ')
                    f.write(f'<{objeto_dato["value"]}> <http://www.w3.org/2000/01/rdf-schema#label> "{label_valor}"@es .\n')
            else:
                valor_limpio = objeto_dato["value"].replace('"', '\\"').replace('\n', ' ')
                f.write(f'<{sujeto}> <{predicado}> "{valor_limpio}" .\n')
            
            tripletas_escritas += 1
            
        f.flush()
        os.fsync(f.fileno())
            
        total_tripletas += tripletas_escritas
        print(f"  -> Se guardaron {tripletas_escritas} tripletas. Total en esta sesión: {total_tripletas}")
        
        offset_actual += TAMANO_BLOQUE
        with open(CHECKPOINT_FILE, "w") as cp:
            cp.write(str(offset_actual))
            
        time.sleep(1)

print("\n✅ Proceso terminado. Sube el archivo 'datos_cine_seguro.ttl' a Blazegraph.")
