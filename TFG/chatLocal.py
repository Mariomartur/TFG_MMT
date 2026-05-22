import ollama
import json
import re
import requests
from SPARQLWrapper import SPARQLWrapper, JSON
from entidades_cine import buscar_id_entidad

with open("mapeo_propiedades.json", "r", encoding="utf-8") as f:
    mapeoProp = json.load(f)
    textoMapeo = json.dumps(mapeoProp, indent=2)

def consultar_llm(prompt, modelo='llama3'):
    response = ollama.chat(model=modelo, messages=[{'role': 'user', 'content': prompt}],
                           options={'temperature':0.0})
    return response['message']['content']

def consultar_llm_stream(prompt, modelo='llama3'):
    response = ollama.chat(model=modelo, messages=[{'role': 'user', 'content': prompt}],
                           options={'temperature':0.0}, stream=True)
    for chunk in response:
        yield chunk['message']['content']

def extraer_entidad(consulta, historial, modelo='llama3'):
    texto_historial = ""
    for msg in historial[-4:]:
        rol = "Usuario" if msg["rol"] == "user" else "Asistente"
        texto_historial += f"{rol}: {msg['contenido']}\n"
  
    prompt_base= f"""Tu única tarea es extraer literalmente el nombre propio (de la película, serie o persona) sobre la que el usuario está preguntando, sin responder a la pregunta.
    Si la frase usa referencias como "él", "ella" o "la película", fíjate en el Historial para saber a qué nombre propio se refiere.
    
    REGLA 1: NO respondas a la pregunta. Si el usuario pide el director de una película, devuélveme el nombre de la película. Si el usuario pide la película de un actor, devuélveme el nombre del actor.
    REGLA 2: Devuelve SOLO el nombre exacto, sin comillas, sin puntos y sin texto extra.
    REGLA 3: Si no encuentras un nombre propio claro, devuelve "None".
    REGLA 4: Devuelve siempre el nombre en el idioma que se ha preguntado

    Ejemplos:
    Frase: "¿Qué películas dirigió Quentin Tarantino?"
    Respuesta: Quentin Tarantino
    Frase: "¿Quién protagonizó Star Wars?"
    Respuesta: Star Wars
    Frase: "¿En qué año salió Matrix?"
    Respuesta: Matrix
    Frase: "Dime peliculas de daniel radcliffe"
    Respuesta: daniel radcliffe
    Frase: "¿Quién produjo la película Avatar?"
    Respuesta: Avatar

    Historial de la conversación reciente:
    {texto_historial}

    Frase actual: "{consulta}"
    Respuesta:
    """
    entidad_buscada = consultar_llm(prompt_base, modelo).strip()
    
    if "Respuesta:" in entidad_buscada:
        entidad_buscada = entidad_buscada.split("Respuesta:")[-1].strip()
    return entidad_buscada


def generar_sparql(consulta, id_entidad, textoMapeo, error_previo="", query_previo="", modelo='llama3'):
    contexto_error = ""
    if error_previo:
        contexto_error = f"""
        ¡ATENCIÓN! Tu intento anterior falló.
        La consulta que generaste fue:
        ```sparql
        {query_previo}
        ```
        Motivo del fallo:
        {error_previo}
        Por favor, corrige la consulta SPARQL para solucionar este problema (por ejemplo, invirtiendo el Sujeto y el Objeto).
        """

    prompt_sparql = f"""
    Eres un traductor experto de lenguaje natural a SPARQL.
    Piensa paso a paso (Chain of Thought) antes de escribir el código.
    
    Esquema de propiedades disponibles:
    {textoMapeo}

    Objetivo: 
    Genera una consulta SPARQL válida para responder a la consulta '{consulta}'
    
    {contexto_error}

    REGLAS:
    1. La entidad principal es: wd:{id_entidad}
    2. Usa SOLO las propiedades del esquema de arriba.
    3. Las propiedades DEBEN llevar el prefijo 'wdt:'. Si usas la propiedad P178, escribe wdt:P178.
    4. El formato debe ser SELECT ?respuesta WHERE {{ ... }}
    5. IMPORTANTE: Si la pregunta busca obras de una persona (ej: películas de un actor/director), invierte el orden lógico: SELECT ?respuesta WHERE {{ ?respuesta wdt:P... wd:{id_entidad} . }}
    6. Si la pregunta es sobre una PELÍCULA (ej: año de Matrix): SELECT ?respuesta WHERE {{ wd:{id_entidad} wdt:P... ?respuesta . }}
    7. IMPORTANTE: "Protagonizada" o "actúa" significa wdt:P161. "Dirigida" significa wdt:P57.
    8. Piensa primero tu lógica en voz alta, y luego devuelve SOLO el código SPARQL dentro de un bloque ```sparql ... ```
    """

    respuesta_sparql = consultar_llm(prompt_sparql, modelo)
    
    razonamiento = respuesta_sparql.split("```")[0].strip()
    if razonamiento:
        print(f"   [Pensamiento LLM]: {razonamiento}")
        
    return traducir_sparql(respuesta_sparql)

def procesar_consulta(consulta, historial=None, st_callback=None, modelo='llama3'):
    if historial is None:
        historial = []
        
    def notify(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            print(msg.encode('ascii', 'replace').decode('ascii'))
        if st_callback:
            st_callback(msg)
        
    print(f"\n--- Procesando: '{consulta}' ---".encode('ascii', 'replace').decode('ascii'))

    entidad_buscada = extraer_entidad(consulta, historial, modelo)
    notify(f"🔍 **Entidad detectada:** `{entidad_buscada}`")

    candidato = buscar_id_entidad(entidad_buscada)
    if isinstance(candidato, list):
        candidato = candidato[0] if candidato else None

    if not candidato:
        yield "No he encontrado esa película o persona en Wikidata. ¿Puedes ser más específico?"
        return
    
    id_entidad = candidato["id"]
    notify(f"🔗 **ID Wikidata:** `{id_entidad}` ({candidato['nombre']})")

    intentos_sparql = 0
    max_intentos = 3
    resultados = None
    query_limpia = ""
    error_previo = ""

    while intentos_sparql < max_intentos:
        query_limpia = generar_sparql(consulta, id_entidad, textoMapeo, error_previo, query_limpia, modelo)
        notify(f"💻 **SPARQL Generado (Intento {intentos_sparql + 1}):**\n```sparql\n{query_limpia}\n```")
        
        resultados, error_db = ejecutar_sparql_local(query_limpia)
        
        if error_db == "CONNECTION_ERROR":
            yield "❌ **Error:** No me puedo conectar a Blazegraph. Asegúrate de que la base de datos está encendida en el puerto 9999."
            return

        if resultados:
            break
        else:
            if error_db:
                error_previo = f"La consulta falló con este error de sintaxis en Blazegraph: {error_db}"
            else:
                error_previo = "La consulta se ejecutó sin errores, pero no devolvió NINGÚN resultado de la base de datos. Comprueba si invertiste el Sujeto y el Objeto. Recuerda que las películas apuntan a los actores/directores, no al revés."
            notify(f"⚠️ **Fallo en ejecución:** {error_previo}\n🔄 **Reintentando...**")
        intentos_sparql += 1

    if not resultados:
        yield "La consulta se generó pero no se encontraron datos en la base de datos local."
        return
    
    valores = []
    for fila in resultados:
        variable = list(fila.keys())[0]
        valores.append(fila[variable]["value"])

    notify(f"📊 **Resultados brutos:** `{valores}`")
    
    nombres = traducir_ids(valores)
    
    notify("✨ **Formateando respuesta...**")
    
    respuesta_estructurada = construir_respuesta(consulta, nombres)
    yield respuesta_estructurada

def construir_respuesta(consulta, dato):
    items = [d.strip() for d in dato.split(",") if d.strip()]
    if not items:
        return "No encontré datos para esa consulta en la base de datos."
    
    dato_verificado = ", ".join(items)
    
    prompt_formato = f"""
    Tienes que presentar este dato exacto al usuario: "{dato_verificado}"
    La pregunta fue: "{consulta}"
    
    REGLAS ABSOLUTAS:
    1. El dato entre comillas es la única verdad. No lo cambies, no lo amplíes.
    2. Si el dato tiene varios elementos separados por comas, menciónalos todos.
    3. Una sola frase. Sin inventar contexto extra.
    4. Responde en español.
    
    Respuesta:
    """
    return consultar_llm(prompt_formato)


# Hasta aquí se recibe la consulta y Llama 3 la procesa para devolver una consulta de Wikidata con la pregunta traducida a SPARQL
# A partir de aquí se traduce el SPARQL generado para resolver la cuestión y contestar en lenguaje natural
def traducir_sparql(respuesta_llm):
    match = re.search(r'```(?:sparql)?(.*?)```', respuesta_llm, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Fallback si el LLM olvida las comillas: extraer desde SELECT
    idx = respuesta_llm.upper().find("SELECT")
    if idx != -1:
        return respuesta_llm[idx:].replace('```', '').replace('`', '').strip()
        
    return respuesta_llm.replace('```sparql', '').replace('```', '').replace('`', '').strip()

def ejecutar_sparql_local(consulta):
    endpoint = "http://localhost:9999/blazegraph/namespace/kb/sparql"
    prefijos = """
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    """
    consulta = prefijos + consulta
    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery(consulta)
    sparql.setReturnFormat(JSON)
    try:
        resultados = sparql.query().convert()
        return resultados["results"]["bindings"], None
    except Exception as e:
        error_str = str(e)
        if "10061" in error_str or "Connection refused" in error_str or "denegó" in error_str:
            return [], "CONNECTION_ERROR"
        return [], error_str

def traducir_ids(lista_valores):
    uris_a_traducir = []
    textos = []
    for val in lista_valores:
        if val.startswith("http://www.wikidata.org/entity/"):
            uris_a_traducir.append(f"<{val}>")
        else:
            textos.append(val)
            
    if not uris_a_traducir:
        return ", ".join(textos)
        
    endpoint = "http://localhost:9999/blazegraph/namespace/kb/sparql"
    sparql = SPARQLWrapper(endpoint)
    
    valores_sparql = " ".join(uris_a_traducir)
    
    query = f"""
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?uri ?label WHERE {{
        VALUES ?uri {{ {valores_sparql} }}
        ?uri rdfs:label ?label .
        FILTER(LANG(?label) = "es" || LANG(?label) = "")
    }}
    """
    
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    
    nombres_traducidos = []
    mapa_traducciones = {}
    
    try:
        resultados = sparql.query().convert()
        for fila in resultados["results"]["bindings"]:
            uri = f"<{fila['uri']['value']}>"
            label = fila["label"]["value"]
            mapa_traducciones[uri] = label
            
        for uri in uris_a_traducir:
            # Si se encuentra en la base local, usamos el label, sino el QID (quitando los < >)
            nombres_traducidos.append(mapa_traducciones.get(uri, uri.split("/")[-1].replace('>', '')))
            
    except Exception as e:
        print(f"Error traduciendo IDs localmente: {e}")
        # En caso de error, devolvemos los QIDs
        nombres_traducidos = [uri.split("/")[-1].replace('>', '') for uri in uris_a_traducir]
        
    return ", ".join(nombres_traducidos + textos)






if __name__ == "__main__":
    respuesta = procesar_consulta("¿Qué películas dirigió Christopher Nolan?")
    print("\n--- RESPUESTA DEL LLM ---")
    print(respuesta)