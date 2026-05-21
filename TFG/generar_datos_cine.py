import time
import os
from SPARQLWrapper import SPARQLWrapper, JSON

sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
sparql.addCustomHttpHeader("User-Agent", "MMT_TFG_Bot/1.0 (m.martinezturpin@um.es)")
sparql.setReturnFormat(JSON)

total_tripletas = 0

CHECKPOINT_FILE = "checkpoint.txt"
ARCHIVO_DATOS = "datos_cine_seguro.ttl"

año_actual = 2026
if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, "r") as f:
        try:
            año_actual = int(f.read().strip())
        except ValueError:
            año_actual = 2026

print(f"🎬 Iniciando extracción masiva de películas por AÑO...")
if año_actual < 2026:
    print(f"Resumiendo desde el año guardado: {año_actual}")

with open(ARCHIVO_DATOS, "a", encoding="utf-8") as f:
    
    while año_actual >= 1950:
        print(f"\nDescargando películas del año {año_actual}...")
        
        query = f"""
        SELECT ?pelicula ?propiedad ?valor ?peliculaLabel ?valorLabel WHERE {{
            {{
                SELECT DISTINCT ?pelicula WHERE {{
                    ?pelicula wdt:P31 wd:Q11424 .
                    ?pelicula wdt:P57 ?director .
                    ?pelicula wdt:P345 ?imdb .
                    ?pelicula wdt:P577 ?fecha .

                    ?pelicula wikibase:sitelinks ?sitelinks .
                    FILTER(?sitelinks >= 10)
                    FILTER(?fecha >= "{año_actual}-01-01T00:00:00Z"^^xsd:dateTime && ?fecha < "{año_actual+1}-01-01T00:00:00Z"^^xsd:dateTime)
                }}
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
                espera = 65
                print(f"Esperando {espera} segundos por el límite de Wikidata antes de reintentar...")
                time.sleep(espera)
        
        if len(resultados) == 0:
            print(f"No se encontraron películas famosas para el año {año_actual}.")
            
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
        
        año_actual -= 1
        with open(CHECKPOINT_FILE, "w") as cp:
            cp.write(str(año_actual))
            
        print("⏳ Esperando 65 segundos para respetar el límite de Wikidata (1 req/min)...")
        time.sleep(65)

print("\n✅ Proceso terminado. Sube el archivo 'datos_cine_seguro.ttl' a Blazegraph.")
