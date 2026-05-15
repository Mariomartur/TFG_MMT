from SPARQLWrapper import SPARQLWrapper, JSON

sparql = SPARQLWrapper("http://localhost:9999/blazegraph/namespace/kb/sparql")

sparql.setQuery("""
    SELECT ?juego ?propiedad ?valor WHERE {
      ?juego ?propiedad ?valor
    } LIMIT 10
""")

sparql.setReturnFormat(JSON)

try:
    print(f"Conectando a endpoint local...")
    results = sparql.query().convert()
    bindings = results['results']['bindings']
    if len(bindings) > 0:
        print(f"{len(bindings)} resultados encontrados")
        print("Ejemplo de dato:", bindings[0])
except Exception as e:
    print("ERROR: ", e)