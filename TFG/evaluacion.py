import json
import time
from chatLocal import extraer_entidad, generar_sparql, textoMapeo
from entidades_cine import buscar_id_entidad

def evaluar_sistema():
    print("Iniciando Evaluación Automática del Sistema (TFG)...")
    
    try:
        with open("dataset_evaluacion.json", "r", encoding="utf-8") as f:
            dataset = json.load(f)
    except FileNotFoundError:
        print("Error: No se encontró 'dataset_evaluacion.json'.")
        return

    total = len(dataset)
    print(f"Cargadas {total} preguntas de prueba.\n")

    modelos_a_evaluar = ['llama3', 'llama3.2:1b', 'mistral', 'gemma2:9b', 'gemma2:2b', 'deepseek-r1:8b']
    resultados_modelos = {}

    for modelo in modelos_a_evaluar:
        print(f"\n" + "="*50)
        print(f"Evaluando modelo: {modelo}")
        print("="*50)
        
        exitos_entidad = 0
        exitos_sparql = 0
        tiempo_total_modelo = 0
        
        for item in dataset:
            print(f"Prueba #{item['id']}: '{item['pregunta']}'")
            start_q = time.time()
            
            # 1. Evaluar Extracción de Entidad
            entidad_obtenida = extraer_entidad(item["pregunta"], historial=[], modelo=modelo)
            if entidad_obtenida.lower() == item["entidad_esperada"].lower():
                print(f"  [OK] Entidad Extraída Correctamente: {entidad_obtenida}")
                exitos_entidad += 1
            else:
                print(f"  [FAIL] Fallo en Entidad. Esperaba '{item['entidad_esperada']}', obtuvo '{entidad_obtenida}'")
                tiempo_q = time.time() - start_q
                tiempo_total_modelo += tiempo_q
                print(f"  [TIEMPO] Pregunta procesada en {tiempo_q:.2f}s")
                continue # Si falla la entidad, no podemos probar el SPARQL
                
            # Obtenemos el ID real (necesario para la generación de SPARQL)
            candidato = buscar_id_entidad(entidad_obtenida)
            if isinstance(candidato, list):
                candidato = candidato[0] if candidato else None
                
            if not candidato:
                print(f"  [WARN] Advertencia: Wikidata no encontró la entidad '{entidad_obtenida}'")
                tiempo_q = time.time() - start_q
                tiempo_total_modelo += tiempo_q
                print(f"  [TIEMPO] Pregunta procesada en {tiempo_q:.2f}s")
                continue
                
            id_entidad = candidato["id"]
            
            # 2. Evaluar Generación de SPARQL
            sparql_generado = generar_sparql(item["pregunta"], id_entidad, textoMapeo, modelo=modelo)
            
            # Para que el SPARQL sea correcto en este test, debe contener la propiedad esperada y el id de la entidad
            if item["propiedad_esperada"] in sparql_generado and id_entidad in sparql_generado:
                print(f"  [OK] SPARQL Generado Correctamente (Contiene {item['propiedad_esperada']} y {id_entidad})")
                exitos_sparql += 1
            else:
                print(f"  [FAIL] Fallo en SPARQL. Esperaba propiedad {item['propiedad_esperada']}.")
                print(f"     SPARQL Generado:\n{sparql_generado}")
                
            tiempo_q = time.time() - start_q
            tiempo_total_modelo += tiempo_q
            print(f"  [TIEMPO] Pregunta procesada en {tiempo_q:.2f}s")
            print("-" * 50)
            time.sleep(0.5) # Pausa para no sobrecargar el LLM o la API
            
        accuracy_entidad = (exitos_entidad / total) * 100
        accuracy_sparql = (exitos_sparql / total) * 100
        tiempo_medio_q = tiempo_total_modelo / total if total > 0 else 0
        
        resultados_modelos[modelo] = {
            "acc_entidad": accuracy_entidad,
            "acc_sparql": accuracy_sparql,
            "tiempo_total": tiempo_total_modelo,
            "tiempo_medio": tiempo_medio_q
        }

    print("\n" + "="*50)
    print("RESULTADOS GLOBALES DE LA EVALUACIÓN")
    print("="*50)
    for mod, res in resultados_modelos.items():
        print(f"Modelo: {mod}")
        print(f" - Precisión Entidad: {res['acc_entidad']:.2f}%")
        print(f" - Precisión SPARQL:  {res['acc_sparql']:.2f}%")
        print(f" - Tiempo Total:      {res['tiempo_total']:.2f}s")
        print(f" - Tiempo Medio/Preg: {res['tiempo_medio']:.2f}s")
        print("-" * 30)

if __name__ == "__main__":
    evaluar_sistema()
