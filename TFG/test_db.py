from SPARQLWrapper import SPARQLWrapper, JSON
import json
sparql = SPARQLWrapper('http://localhost:9999/blazegraph/namespace/kb/sparql')
query = '''
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wd: <http://www.wikidata.org/entity/>
SELECT ?label ?director_label ?cast_label ?year WHERE {
    ?s wdt:P31 wd:Q11424 .
    ?s wdt:P57 ?director .
    ?director rdfs:label ?director_label .
    FILTER(LANG(?director_label) = 'es' || LANG(?director_label) = 'en')
    ?s wdt:P161 ?cast .
    ?cast rdfs:label ?cast_label .
    FILTER(LANG(?cast_label) = 'es' || LANG(?cast_label) = 'en')
    ?s wdt:P577 ?date .
    BIND(YEAR(?date) AS ?year)
    ?s rdfs:label ?label .
    FILTER(LANG(?label) = 'es' || LANG(?label) = 'en')
} LIMIT 100
'''
sparql.setQuery(query)
sparql.setReturnFormat(JSON)
res = sparql.query().convert()
for i in res['results']['bindings']:
    print(i['label']['value'])
