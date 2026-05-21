import json
import time
import sys
from chatLocal import extraer_entidad, generar_sparql, textoMapeo, ejecutar_sparql_local
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

    if len(sys.argv) > 1:
        modelos_a_evaluar = [sys.argv[1]]
    else:
        print("Modelos típicos: llama3, llama3.2:1b, mistral, gemma2:9b, gemma2:2b, deepseek-r1:8b")
        modelo_input = input("Introduce el nombre del modelo que quieres evaluar: ").strip()
        if not modelo_input:
            print("No se introdujo ningún modelo. Usando 'llama3' por defecto...")
            modelos_a_evaluar = ['llama3']
        else:
            modelos_a_evaluar = [modelo_input]

    resultados_modelos = {}

    for modelo in modelos_a_evaluar:
        print(f"\n" + "="*50)
        print(f"Evaluando modelo: {modelo}")
        print("="*50)
        
        exitos_entidad = 0
        exitos_sparql_zero_shot = 0
        exitos_sparql_final = 0
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
            
            # 2. Evaluar Generación de SPARQL (Ablación: Zero-Shot vs Reflexión)
            intentos = 0
            max_intentos = 3
            query_limpia = ""
            error_previo = ""
            exito_en_este_item = False
            exito_zero_shot = False
            
            while intentos < max_intentos:
                query_limpia = generar_sparql(item["pregunta"], id_entidad, textoMapeo, error_previo, query_limpia, modelo=modelo)
                
                contiene_esperado = item["propiedad_esperada"] in query_limpia and id_entidad in query_limpia
                resultados, error_db = ejecutar_sparql_local(query_limpia)
                
                if error_db == "CONNECTION_ERROR":
                    print("  [ERROR] No se pudo conectar a Blazegraph (Docker no está encendido).")
                    break
                
                if contiene_esperado and not error_db:
                    exito_en_este_item = True
                    if intentos == 0:
                        exito_zero_shot = True
                        print(f"  [OK] Zero-Shot: SPARQL Generado Correctamente (Contiene {item['propiedad_esperada']} y {id_entidad})")
                    else:
                        print(f"  [OK] Reflexión: SPARQL Corregido en intento {intentos + 1}.")
                    break
                else:
                    if error_db:
                        error_previo = f"La consulta falló con este error de sintaxis: {error_db}"
                    else:
                        error_previo = f"Falta la propiedad {item['propiedad_esperada']} o el ID {id_entidad}, revisa la semántica."
                    
                    if intentos == 0:
                        print(f"  [WARN] Zero-Shot Fallido. Iniciando Bucle de Reflexión...")
                
                intentos += 1
            
            if exito_zero_shot:
                exitos_sparql_zero_shot += 1
            if exito_en_este_item:
                exitos_sparql_final += 1
            else:
                print(f"  [FAIL] Fallo tras {max_intentos} intentos. Esperaba propiedad {item['propiedad_esperada']}.")
                print(f"     Último SPARQL Generado:\n{query_limpia}")
                
            tiempo_q = time.time() - start_q
            tiempo_total_modelo += tiempo_q
            print(f"  [TIEMPO] Pregunta procesada en {tiempo_q:.2f}s")
            print("-" * 50)
            time.sleep(0.5) # Pausa para no sobrecargar el LLM o la API
            
        accuracy_entidad = (exitos_entidad / total) * 100
        accuracy_sparql_zero_shot = (exitos_sparql_zero_shot / total) * 100
        accuracy_sparql_final = (exitos_sparql_final / total) * 100
        tiempo_medio_q = tiempo_total_modelo / total if total > 0 else 0
        
        resultados_modelos[modelo] = {
            "acc_entidad": accuracy_entidad,
            "acc_sparql_zs": accuracy_sparql_zero_shot,
            "acc_sparql_final": accuracy_sparql_final,
            "tiempo_total": tiempo_total_modelo,
            "tiempo_medio": tiempo_medio_q
        }

    print("\n" + "="*50)
    print("RESULTADOS GLOBALES DE LA EVALUACIÓN")
    print("="*50)
    for mod, res in resultados_modelos.items():
        print(f"Modelo: {mod}")
        print(f" - Precisión Entidad:      {res['acc_entidad']:.2f}%")
        print(f" - Precisión Zero-Shot:    {res['acc_sparql_zs']:.2f}%")
        print(f" - Precisión con Reflexión:{res['acc_sparql_final']:.2f}%")
        print(f" - Mejora por Reflexión:   {(res['acc_sparql_final'] - res['acc_sparql_zs']):.2f}%")
        print(f" - Tiempo Total:           {res['tiempo_total']:.2f}s")
        print(f" - Tiempo Medio/Preg:      {res['tiempo_medio']:.2f}s")
        print("-" * 30)

if __name__ == "__main__":
    evaluar_sistema()
