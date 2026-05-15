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
    exitos_entidad = 0
    exitos_sparql = 0

    print(f"Cargadas {total} preguntas de prueba.\n")

    for item in dataset:
        print(f"Prueba #{item['id']}: '{item['pregunta']}'")
        
        # 1. Evaluar Extracción de Entidad
        entidad_obtenida = extraer_entidad(item["pregunta"], historial=[])
        if entidad_obtenida.lower() == item["entidad_esperada"].lower():
            print(f"  [OK] Entidad Extraída Correctamente: {entidad_obtenida}")
            exitos_entidad += 1
        else:
            print(f"  [FAIL] Fallo en Entidad. Esperaba '{item['entidad_esperada']}', obtuvo '{entidad_obtenida}'")
            continue # Si falla la entidad, no podemos probar el SPARQL
            
        # Obtenemos el ID real (necesario para la generación de SPARQL)
        candidato = buscar_id_entidad(entidad_obtenida)
        if isinstance(candidato, list):
            candidato = candidato[0] if candidato else None
            
        if not candidato:
            print(f"  [WARN] Advertencia: Wikidata no encontró la entidad '{entidad_obtenida}'")
            continue
            
        id_entidad = candidato["id"]
        
        # 2. Evaluar Generación de SPARQL
        sparql_generado = generar_sparql(item["pregunta"], id_entidad, textoMapeo)
        
        # Para que el SPARQL sea correcto en este test, debe contener la propiedad esperada y el id de la entidad
        if item["propiedad_esperada"] in sparql_generado and id_entidad in sparql_generado:
            print(f"  [OK] SPARQL Generado Correctamente (Contiene {item['propiedad_esperada']} y {id_entidad})")
            exitos_sparql += 1
        else:
            print(f"  [FAIL] Fallo en SPARQL. Esperaba propiedad {item['propiedad_esperada']}.")
            print(f"     SPARQL Generado:\n{sparql_generado}")
            
        print("-" * 50)
        time.sleep(0.5) # Pausa para no sobrecargar el LLM o la API
        
    # Calcular Métricas (Accuracy)
    accuracy_entidad = (exitos_entidad / total) * 100
    accuracy_sparql = (exitos_sparql / total) * 100

    print("\n" + "="*50)
    print("RESULTADOS DE LA EVALUACIÓN (Para la memoria del TFG)")
    print("="*50)
    print(f"Total de preguntas evaluadas: {total}")
    print(f"Precisión en Extracción de Entidad: {accuracy_entidad:.2f}% ({exitos_entidad}/{total})")
    print(f"Precisión en Generación SPARQL:     {accuracy_sparql:.2f}% ({exitos_sparql}/{total})")
    print("="*50)

if __name__ == "__main__":
    evaluar_sistema()
