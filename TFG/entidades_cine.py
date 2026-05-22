import requests
from SPARQLWrapper import SPARQLWrapper, JSON

def buscar_id_entidad(nombre_entidad):
    """
    Busca una entidad por label directamente en Blazegraph local.
    Sin dependencia de red externa.
    """
    sparql = SPARQLWrapper("http://localhost:9999/blazegraph/namespace/kb/sparql")
    sparql.setReturnFormat(JSON)

    # Búsqueda exacta primero (case-insensitive)
    query_exacta = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>

    SELECT DISTINCT ?entidad ?label WHERE {{
        ?entidad rdfs:label ?label .
        FILTER(LCASE(STR(?label)) = LCASE("{nombre_entidad}"))
        ?entidad ?p ?o .
    }}
    LIMIT 5
    """

    try:
        sparql.setQuery(query_exacta)
        res = sparql.query().convert()
        bindings = res["results"]["bindings"]

        if bindings:
            item = bindings[0]
            qid = item["entidad"]["value"].split("/")[-1]
            label = item["label"]["value"]
            return {"id": qid, "nombre": label}

        
        query_parcial = f"""
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX wd: <http://www.wikidata.org/entity/>

        SELECT DISTINCT ?entidad ?label WHERE {{
            ?entidad rdfs:label ?label .
            FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{nombre_entidad}")))
            ?entidad ?p ?o .
        }}
        LIMIT 5
        """
        sparql.setQuery(query_parcial)
        res = sparql.query().convert()
        bindings = res["results"]["bindings"]

        if bindings:
            item = bindings[0]
            qid = item["entidad"]["value"].split("/")[-1]
            label = item["label"]["value"]
            return {"id": qid, "nombre": label}

        return None

    except Exception as e:
        print(f"Error buscando entidad localmente: {e}")
        return None

if __name__ == "__main__":
    print(buscar_id_entidad("Jurassic Park"))
    print(buscar_id_entidad("Christopher Nolan"))
    print(buscar_id_entidad("Daniel Radcliffe"))
    print(buscar_id_entidad("Los Vengadores"))
    print(buscar_id_entidad("Robert Downey Jr"))
    print(buscar_id_entidad("Harry Potter"))
    print(buscar_id_entidad("Matrix"))