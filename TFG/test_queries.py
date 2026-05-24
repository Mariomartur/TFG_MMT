from SPARQLWrapper import SPARQLWrapper, JSON

def query_kg(q):
    sparql = SPARQLWrapper('http://localhost:9999/blazegraph/namespace/kb/sparql')
    sparql.setQuery(q)
    sparql.setReturnFormat(JSON)
    try:
        return sparql.query().convert()['results']['bindings']
    except Exception as e:
        print(f'Error: {e}')
        return []

def get_prop(movie, prop):
    q = f'''
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    PREFIX wd: <http://www.wikidata.org/entity/>
    SELECT DISTINCT ?valLabel WHERE {{
        ?s rdfs:label '{movie}'@es ;
           wdt:{prop} ?val .
        OPTIONAL {{
            ?val rdfs:label ?valLabel .
            FILTER(LANG(?valLabel) = 'es' || LANG(?valLabel) = 'en')
        }}
    }} LIMIT 5
    '''
    res = query_kg(q)
    vals = [r.get('valLabel', {}).get('value', r.get('val', {}).get('value', '')) for r in res]
    print(f'{movie} {prop}: {vals}')

def get_prop_en(movie, prop):
    q = f'''
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    PREFIX wd: <http://www.wikidata.org/entity/>
    SELECT DISTINCT ?valLabel WHERE {{
        ?s rdfs:label '{movie}'@en ;
           wdt:{prop} ?val .
        OPTIONAL {{
            ?val rdfs:label ?valLabel .
            FILTER(LANG(?valLabel) = 'es' || LANG(?valLabel) = 'en')
        }}
    }} LIMIT 5
    '''
    res = query_kg(q)
    vals = [r.get('valLabel', {}).get('value', r.get('val', {}).get('value', '')) for r in res]
    print(f'{movie} (en) {prop}: {vals}')

get_prop('Amélie', 'P161') # actores
get_prop('Amélie', 'P577') # año
get_prop('Joker', 'P136') # género
get_prop_en('Joker', 'P136') # género
get_prop_en('The Dark Knight', 'P136')
get_prop_en('Avatar', 'P577')
get_prop_en('The Matrix', 'P577')
get_prop_en('The Godfather', 'P161')
get_prop_en('The Godfather', 'P345')
get_prop_en('The Godfather', 'P495')
get_prop_en('The Godfather', 'P364')
get_prop_en('The Godfather', 'P2130')
get_prop_en('The Godfather', 'P166')
get_prop_en('Psycho', 'P345')
get_prop_en('Avatar', 'P162')
get_prop_en('Avatar', 'P2047')
get_prop('Joker', 'P495')
get_prop_en('Joker', 'P495')
get_prop_en('Joker', 'P2047')
get_prop_en('Joker', 'P58')
get_prop_en('Joker', 'P166')
get_prop('Matrix', 'P495')
get_prop('Matrix', 'P364')

get_prop_en('Quentin Tarantino', 'P57') # movies of tarantino - wait, P57 is inverted.

def get_movies_of_director(director):
    q = f'''
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    PREFIX wd: <http://www.wikidata.org/entity/>
    SELECT DISTINCT ?label WHERE {{
        ?dir rdfs:label '{director}'@es .
        ?s wdt:P57 ?dir ;
           rdfs:label ?label .
        FILTER(LANG(?label) = 'es')
    }} LIMIT 5
    '''
    res = query_kg(q)
    vals = [r['label']['value'] for r in res]
    print(f'{director} movies: {vals}')

get_movies_of_director('Quentin Tarantino')
get_movies_of_director('Ridley Scott')
get_movies_of_director('Steven Spielberg')
