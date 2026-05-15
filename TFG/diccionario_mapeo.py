from SPARQLWrapper import SPARQLWrapper, JSON
import json
import re

endpoint = "http://localhost:9999/blazegraph/namespace/kb/sparql"
sparql = SPARQLWrapper(endpoint)

# Se sacan las propiedades una a una
sparql.setQuery("""
                SELECT DISTINCT ?propiedad WHERE {
                ?juego ?propiedad ?valor
                }
                """)

sparql.setReturnFormat(JSON)

results= sparql.query().convert()
properties = {}

for result in results["results"]["bindings"]:
    url_property = result["propiedad"]["value"]
    #Esta expresión regular nos filtra las propiedades de Wikidata P+numeros
    match = re.search(r'P\d+', url_property)
    if match:
        id_prop = match.group(0)
        properties[id_prop] = ""

with open("mapeo_propiedades.json", "w", encoding="utf-8") as f:
    json.dump(properties, f, indent=4)

print(f"Se han encontrado {len(properties)} propiedades y se ha creado el archivo 'mapeo_propiedades.json'")

