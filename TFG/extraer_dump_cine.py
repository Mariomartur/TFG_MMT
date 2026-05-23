import bz2
import time
import os

DUMP_FILE = "latest-truthy.nt.bz2"
OUTPUT_FILE = "datos_cine_dump.nt"

# URIs en bytes para procesamiento ultrarrápido
PROPIEDADES = {
    b"<http://www.wikidata.org/prop/direct/P57>",    # Director
    b"<http://www.wikidata.org/prop/direct/P161>",   # Reparto
    b"<http://www.wikidata.org/prop/direct/P136>",   # Género
    b"<http://www.wikidata.org/prop/direct/P577>",   # Fecha de publicación
    b"<http://www.wikidata.org/prop/direct/P162>",   # Productor
    b"<http://www.wikidata.org/prop/direct/P345>",   # ID IMDb
    b"<http://www.wikidata.org/prop/direct/P495>",   # País de origen
    b"<http://www.wikidata.org/prop/direct/P2047>",  # Duración
    b"<http://www.wikidata.org/prop/direct/P364>",   # Idioma original
    b"<http://www.wikidata.org/prop/direct/P58>",    # Guionista
    b"<http://www.wikidata.org/prop/direct/P166>",   # Premio recibido
    b"<http://www.wikidata.org/prop/direct/P2130>"   # Presupuesto
}

# Propiedades extra para actores, directores, etc.
PROPIEDADES_RELACIONADAS = {
    b"<http://www.wikidata.org/prop/direct/P569>",   # Fecha de nacimiento
    b"<http://www.wikidata.org/prop/direct/P570>",   # Fecha de fallecimiento
    b"<http://www.wikidata.org/prop/direct/P19>",    # Lugar de nacimiento
    b"<http://www.wikidata.org/prop/direct/P27>",    # País de nacionalidad
    b"<http://www.wikidata.org/prop/direct/P106>"    # Ocupación
}

MOVIE_SIGNATURE = b"<http://www.wikidata.org/prop/direct/P31> <http://www.wikidata.org/entity/Q11424>"
LABEL_PRED = b"<http://www.w3.org/2000/01/rdf-schema#label>"

def time_str(start):
    return f"{(time.time() - start) / 60:.1f} min"

def main():
    if not os.path.exists(DUMP_FILE):
        print(f"==================================================")
        print(f" ERROR: No se encuentra '{DUMP_FILE}'.")
        print(f" Descárgalo ejecutando en tu terminal de comandos:")
        print(f" curl -O https://dumps.wikimedia.org/wikidatawiki/latest/wikidata-latest-truthy.nt.bz2")
        print(f"==================================================")
        return

    peliculas = set()
    entidades_relacionadas = set()
    
    # ── PASADA 1: Identificar películas ──
    print("=== PASADA 1: Buscando todas las películas ===")
    t0 = time.time()
    with bz2.open(DUMP_FILE, "rb") as f:
        for i, line in enumerate(f):
            if i % 25000000 == 0 and i > 0:
                print(f"  Leídas {i:,} líneas... ({time_str(t0)})")
            
            if MOVIE_SIGNATURE in line:
                # line format: <sujeto> <pred> <obj> .
                subject = line.split(b" ", 1)[0]
                peliculas.add(subject)
                
    print(f"✅ Pasada 1 terminada. Encontradas {len(peliculas):,} películas. Tiempo: {time_str(t0)}\n")

    # ── PASADA 2: Extraer propiedades de películas ──
    print("=== PASADA 2: Extrayendo propiedades de las películas ===")
    t1 = time.time()
    with bz2.open(DUMP_FILE, "rb") as f, open(OUTPUT_FILE, "wb") as out:
        for i, line in enumerate(f):
            if i % 25000000 == 0 and i > 0:
                print(f"  Leídas {i:,} líneas... ({time_str(t1)})")
                
            parts = line.split(b" ", 2)
            if len(parts) < 3: continue
            
            sujeto = parts[0]
            if sujeto in peliculas:
                pred = parts[1]
                
                # Guardar que es una película
                if pred == b"<http://www.wikidata.org/prop/direct/P31>":
                    if parts[2].startswith(b"<http://www.wikidata.org/entity/Q11424>"):
                        out.write(line)
                        continue
                
                # Guardar las propiedades elegidas
                if pred in PROPIEDADES:
                    out.write(line)
                    obj = parts[2]
                    
                    # Si el valor de la propiedad es otra entidad (ej: el ID del actor Brad Pitt),
                    # nos lo guardamos para en la pasada 3 sacarle el nombre.
                    if obj.startswith(b"<http://www.wikidata.org/entity/Q"):
                        # Extraemos solo el URI sin el ' .\n' del final de N-Triples
                        obj_uri = obj.rsplit(b" ", 1)[0]
                        entidades_relacionadas.add(obj_uri)
                        
    print(f"✅ Pasada 2 terminada. {len(entidades_relacionadas):,} entidades relacionadas encontradas. Tiempo: {time_str(t1)}\n")

    # ── PASADA 3: Extraer propiedades de las entidades relacionadas ──
    print("=== PASADA 3: Extrayendo propiedades de actores, directores... (nacimiento, país...) ===")
    t2 = time.time()
    entidades_segundo_grado = set()
    with bz2.open(DUMP_FILE, "rb") as f, open(OUTPUT_FILE, "ab") as out:
        for i, line in enumerate(f):
            if i % 25000000 == 0 and i > 0:
                print(f"  Leídas {i:,} líneas... ({time_str(t2)})")
                
            parts = line.split(b" ", 2)
            if len(parts) < 3: continue
            
            sujeto = parts[0]
            if sujeto in entidades_relacionadas:
                pred = parts[1]
                if pred in PROPIEDADES_RELACIONADAS:
                    out.write(line)
                    obj = parts[2]
                    # Si la propiedad apunta a otra entidad (ej: ciudad de nacimiento), nos la guardamos
                    if obj.startswith(b"<http://www.wikidata.org/entity/Q"):
                        obj_uri = obj.rsplit(b" ", 1)[0]
                        entidades_segundo_grado.add(obj_uri)
                        
    print(f"✅ Pasada 3 terminada. {len(entidades_segundo_grado):,} entidades de segundo grado encontradas. Tiempo: {time_str(t2)}\n")

    # ── PASADA 4: Extraer etiquetas en español ──
    print("=== PASADA 4: Buscando nombres en español para absolutamente todo ===")
    t3 = time.time()
    with bz2.open(DUMP_FILE, "rb") as f, open(OUTPUT_FILE, "ab") as out:
        todas_las_entidades = peliculas.union(entidades_relacionadas).union(entidades_segundo_grado)
        
        for i, line in enumerate(f):
            if i % 25000000 == 0 and i > 0:
                print(f"  Leídas {i:,} líneas... ({time_str(t3)})")
                
            if LABEL_PRED in line and b'"@es ' in line:
                parts = line.split(b" ", 2)
                if len(parts) < 3: continue
                sujeto = parts[0]
                if sujeto in todas_las_entidades:
                    out.write(line)
                    
    print(f"✅ Pasada 4 terminada. Tiempo: {time_str(t3)}\n")
    print(f"🎉 Proceso completo finalizado. ¡Datos guardados en '{OUTPUT_FILE}'!")
    print("Este archivo .nt ya puede importarse directamente en Blazegraph.")

if __name__ == "__main__":
    main()
