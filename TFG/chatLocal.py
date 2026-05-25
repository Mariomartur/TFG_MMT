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
    url = "http://127.0.0.1:11434/api/chat"
    data = {
        "model": modelo,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0.0}
    }
    # Timeout de 180s para lecturas
    response = requests.post(url, json=data, timeout=180)
    response.raise_for_status()
    return response.json()['message']['content']

def consultar_llm_stream(prompt, modelo='llama3'):
    url = "http://127.0.0.1:11434/api/chat"
    data = {
        "model": modelo,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "options": {"temperature": 0.0}
    }
    response = requests.post(url, json=data, stream=True, timeout=180)
    response.raise_for_status()
    for line in response.iter_lines():
        if line:
            chunk = json.loads(line)
            if 'message' in chunk and 'content' in chunk['message']:
                yield chunk['message']['content']

def extraer_entidad(consulta, historial, ultima_entidad=None,modelo='llama3'):
    texto_historial = ""
    for msg in historial[-4:]:
        rol = "Usuario" if msg["rol"] == "user" else "Asistente"
        texto_historial += f"{rol}: {msg['contenido']}\n"

    contexto_entidad = ""
    if ultima_entidad:
        contexto_entidad = f"""
    CONTEXTO IMPORTANTE: La entidad sobre la que se habló en el turno anterior fue exactamente: "{ultima_entidad}"
    Si la pregunta actual es un seguimiento (usa "él", "ella", "la película", "ese", "esa", "su", o no menciona ninguna entidad nueva),
    devuelve EXACTAMENTE "{ultima_entidad}" sin traducir ni modificar ni una letra.
    """
  
    prompt_base = f"""Tu única tarea es extraer literalmente el nombre propio (de la película, serie o persona) sobre la que el usuario está preguntando.
    NO respondas a la pregunta del usuario, solo extrae la entidad de la que habla.
    
    REGLA 1: Debes envolver el nombre exacto de la entidad entre las etiquetas <entidad> y </entidad>.
    REGLA 2: Si el usuario pide el director de una película, la entidad es la película. Si pide la película de un actor, la entidad es el actor.
    REGLA 3: Si no hay un nombre propio claro, devuelve <entidad>None</entidad>.
    REGLA 4: No añadas ningún otro texto explicativo, solo la etiqueta con la entidad dentro.

    {contexto_entidad}

    Ejemplos:
    Frase: "¿Qué películas dirigió Quentin Tarantino?"
    Respuesta: <entidad>Quentin Tarantino</entidad>
    Frase: "¿Quién protagonizó Star Wars?"
    Respuesta: <entidad>Star Wars</entidad>
    Frase: "¿En qué año salió Matrix?"
    Respuesta: <entidad>Matrix</entidad>
    Frase: "Dime peliculas de daniel radcliffe"
    Respuesta: <entidad>daniel radcliffe</entidad>
    Frase: "¿Quién produjo la película Avatar?"
    Respuesta: <entidad>Avatar</entidad>

    Historial de la conversación reciente:
    {texto_historial}

    Frase actual: "{consulta}"
    Respuesta:
    """
    respuesta_llm = consultar_llm(prompt_base, modelo).strip()
    
    match = re.search(r'<entidad>(.*?)</entidad>', respuesta_llm, re.IGNORECASE | re.DOTALL)
    if match:
        entidad_buscada = match.group(1).strip()
    else:
        # Fallback por si acaso no usó las etiquetas
        entidad_buscada = respuesta_llm.replace("Respuesta:", "").strip()
        
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
    8. MULTI-HOP: Si la pregunta requiere dos saltos (ej: lugar de nacimiento del director de Dune), usa una variable intermedia: SELECT ?respuesta WHERE {{ wd:{id_entidad} wdt:P57 ?director . ?director wdt:P19 ?respuesta . }}
    9. Piensa primero tu lógica en voz alta, y luego devuelve SOLO el código SPARQL dentro de un bloque ```sparql ... ```
    """

    respuesta_sparql = consultar_llm(prompt_sparql, modelo)
    
    razonamiento = respuesta_sparql.split("```")[0].strip()
    if razonamiento:
        print(f"   [Pensamiento LLM]: {razonamiento}")
        
    return traducir_sparql(respuesta_sparql)

def procesar_consulta(consulta, historial=None, st_callback=None, ultima_entidad=None, modelo='llama3'):
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

    entidad_buscada = extraer_entidad(consulta, historial, ultima_entidad, modelo)
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
    
    notify("✨ **Generando respuesta en lenguaje natural...**")

    tipo_dato = inferir_tipo(query_limpia)

    prompt_nat = f"""
    Eres un asistente experto en cine con un tono cercano y natural.
    
    Pregunta del usuario: "{consulta}"
    Tipo de dato: {tipo_dato}
    Datos reales de la base de datos: {nombres}

    INSTRUCCIONES DE FORMATO según el tipo de dato:
    - Si son PERSONAS (actores, directores, productores):
        Presenta con dos puntos y lista: "Los actores son: Nombre1, Nombre2 y Nombre3."
        Si son muchos (más de 6), menciona los primeros 5 y añade "entre otros."
    - Si es una FECHA o AÑO:
        Responde en una frase natural: "nombrepelicula se estrenó en 2014."
    - Si es un GÉNERO:
        "nombrepelicula es una película de crimen y drama."
    - Si es un ID o CÓDIGO (IMDb):
        "El identificador de nombrepelicula en IMDb es tt1375666."
    - Si es una DURACIÓN:
        Convierte los minutos a formato legible: "nombrepelicula dura 3 horas y 14 minutos."
    - Si es un PRESUPUESTO:
        Convierte el número a millones: "El presupuesto de nombrepelicula fue de unos 237 millones de dólares."
    - Si es un PAÍS:
        "nombrepelicula es una película francesa."
    - Si son PELÍCULAS (filmografía de alguien):
        "Entre las películas de nombredirector están: nombrepelicula1, nombrepelicula2 y nombrepelicula3, entre otras."

    REGLAS:
    1. Usa SOLO los datos proporcionados. No añadas nada más.
    2. Responde siempre en español.
    3. Sé natural y conversacional, no robótico.
    4. No empieces con "¡Claro!" ni con emojis ni risas.
    5. Si solo vas a responder con una entidad, genera la respuesta en singular.
    """

    for chunk in consultar_llm_stream(prompt_nat, modelo):
        yield chunk


def inferir_tipo(query_sparql: str) -> str:
    """
    Detecta qué tipo de dato devuelve la query para ayudar al LLM a formatear.
    """
    q = query_sparql.upper()
    if "P161" in q: return "PERSONAS (actores/reparto)"
    if "P57"  in q: return "PERSONAS (directores) o PELÍCULAS (filmografía)"
    if "P162" in q: return "PERSONAS (productores)"
    if "P58"  in q: return "PERSONAS (guionistas)"
    if "P577" in q: return "FECHA DE ESTRENO"
    if "P136" in q: return "GÉNERO cinematográfico"
    if "P345" in q: return "CÓDIGO IMDb"
    if "P2047"in q: return "DURACIÓN en minutos"
    if "P2130"in q: return "PRESUPUESTO en dólares"
    if "P495" in q: return "PAÍS DE ORIGEN"
    if "P364" in q: return "IDIOMA ORIGINAL"
    if "P166" in q: return "PREMIOS recibidos"
    return "DATO general"

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
    endpoint = "http://127.0.0.1:9999/blazegraph/namespace/kb/sparql"
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
        
    endpoint = "http://127.0.0.1:9999/blazegraph/namespace/kb/sparql"
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