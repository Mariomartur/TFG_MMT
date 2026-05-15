import requests
from SPARQLWrapper import SPARQLWrapper, JSON

def buscar_id_entidad(nombre_entidad):
    """
    Busca una entidad usando la API de Wikidata (para evitar límites de SPARQL)
    y prioriza las que existan en nuestra base de datos local.
    """
    url = "https://www.wikidata.org/w/api.php"
    params = {
        "action": "wbsearchentities",
        "search": nombre_entidad,
        "language": "es",
        "format": "json",
        "limit": 10
    }
    headers = {
        'User-Agent': 'MMT_TFG_Bot/1.0 (m.martinezturpin@um.es)'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        data = response.json()
        
        resultados = data.get("search", [])
        if not resultados:
            return None
            
        qids = [item["id"] for item in resultados]
        
        # Filtramos con la base de datos local para coger el QID correcto (pelicula/actor)
        sparql_local = SPARQLWrapper("http://localhost:9999/blazegraph/namespace/kb/sparql")
        values = " ".join([f"wd:{q}" for q in qids])
        
        query_local = f"""
        PREFIX wd: <http://www.wikidata.org/entity/>
        SELECT ?id WHERE {{
            VALUES ?id {{ {values} }}
            ?id ?p ?o .
        }} GROUP BY ?id LIMIT 10
        """
        sparql_local.setQuery(query_local)
        sparql_local.setReturnFormat(JSON)
        
        try:
            res_local = sparql_local.query().convert()
            found_qids = [b["id"]["value"].split("/")[-1] for b in res_local["results"]["bindings"]]
            
            # Devolver el primer resultado de la API que exista en nuestra DB local
            for item in resultados:
                if item["id"] in found_qids:
                    return {"id": item["id"], "nombre": item["label"]}
        except Exception as local_e:
            print(f"Aviso: no se pudo filtrar localmente: {local_e}")
            
        # Fallback: si ninguno está en la local (o falló), devolvemos el primero de la API
        primer_item = resultados[0]
        return {"id": primer_item["id"], "nombre": primer_item["label"]}
        
    except Exception as e:
        print(f"Error en la desambiguación con API de Wikidata: {e}")
        return None

# --- Prueba ---
if __name__ == "__main__":
    print(buscar_id_entidad("Up")) # Debería sacar la película, no la preposición
    print(buscar_id_entidad("Christopher Nolan")) # Debería sacar al director (humano)