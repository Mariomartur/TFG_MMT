# Ejemplo conceptual usando SPARQLWrapper
from SPARQLWrapper import SPARQLWrapper, JSON

sparql = SPARQLWrapper("https://query.wikidata.org/sparql") # Esto luego será http://localhost:9999/blazegraph/...
sparql.setQuery("""
    SELECT ?itemLabel WHERE {
      wd:Q7251 wdt:P19 ?item.      # Q7251 = Turing, P19 = Lugar de nacimiento
      SERVICE wikibase:label { bd:serviceParam wikibase:language "es". }
    }
""")
sparql.setReturnFormat(JSON)
results = sparql.query().convert()
print(results)