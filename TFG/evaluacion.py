import json
import time
import sys
import concurrent.futures
from chatLocal import extraer_entidad, generar_sparql, textoMapeo, ejecutar_sparql_local, traducir_ids
from entidades_cine import buscar_id_entidad


def verificar_respuesta(dato_obtenido: str, items_esperados: list[str]) -> bool:
    """
    Comprueba si la cadena de datos obtenida de Blazegraph contiene
    al menos uno de los valores esperados (case-insensitive).

    Se compara sobre el dato traducido (nombres reales), no sobre QIDs.
    """
    dato_lower = dato_obtenido.lower()
    return any(item.lower() in dato_lower for item in items_esperados)


def evaluar_pregunta(item: dict, modelo: str) -> dict:
    """
    Ejecuta las tres fases de evaluación para una sola pregunta y
    devuelve un dict con los resultados detallados.
    """
    resultado = {
        "id": item["id"],
        "pregunta": item["pregunta"],
        "exito_entidad": False,
        "entidad_obtenida": None,
        "id_wikidata": None,
        "exito_sparql_zero_shot": False,
        "exito_sparql_final": False,
        "intentos_usados": 0,
        "exito_respuesta": None,
        "dato_obtenido": None,
        "ultimo_sparql": "",
        "tiempo": 0.0,
        "error": None,
    }

    start = time.time()

    # ── FASE 1: Extracción de entidad ──────────────────────────────────────
    entidad_obtenida = extraer_entidad(item["pregunta"], historial=[], modelo=modelo)
    resultado["entidad_obtenida"] = entidad_obtenida

    if entidad_obtenida.lower() != item["entidad_esperada"].lower():
        print(f"  [FAIL] Entidad. Esperaba '{item['entidad_esperada']}', obtuvo '{entidad_obtenida}'")
        resultado["tiempo"] = time.time() - start
        return resultado

    resultado["exito_entidad"] = True
    print(f"  [OK]   Entidad: '{entidad_obtenida}'")

    # ── Resolución del ID local ────────────────────────────────────────────
    candidato = buscar_id_entidad(entidad_obtenida)
    if isinstance(candidato, list):
        candidato = candidato[0] if candidato else None

    if not candidato:
        print(f"  [WARN] Entidad '{entidad_obtenida}' no encontrada en la base de datos local.")
        resultado["error"] = "entidad_no_encontrada_local"
        resultado["tiempo"] = time.time() - start
        return resultado

    id_entidad = candidato["id"]
    resultado["id_wikidata"] = id_entidad
    print(f"  [INFO] ID Wikidata: {id_entidad} ({candidato['nombre']})")

    # ── FASE 2: Generación y ejecución de SPARQL ───────────────────────────
    max_intentos = 3
    query_limpia = ""
    error_previo = ""

    for intento in range(max_intentos):
        query_limpia = generar_sparql(
            item["pregunta"], id_entidad, textoMapeo,
            error_previo, query_limpia, modelo=modelo
        )
        resultado["ultimo_sparql"] = query_limpia


        estructura_correcta = (
            item["propiedad_esperada"] in query_limpia and
            id_entidad in query_limpia
        )

        resultados_db, error_db = ejecutar_sparql_local(query_limpia)

        if error_db == "CONNECTION_ERROR":
            print("  [ERROR] Sin conexión a Blazegraph.")
            resultado["error"] = "blazegraph_offline"
            resultado["tiempo"] = time.time() - start
            return resultado

        if estructura_correcta and not error_db:
            resultado["intentos_usados"] = intento + 1
            if intento == 0:
                resultado["exito_sparql_zero_shot"] = True
                resultado["exito_sparql_final"] = True
                print(f"  [OK]   SPARQL Zero-Shot correcto (contiene {item['propiedad_esperada']})")
            else:
                resultado["exito_sparql_final"] = True
                print(f"  [OK]   SPARQL corregido en intento {intento + 1}")
            break

        if error_db:
            error_previo = f"Error de sintaxis en Blazegraph: {error_db}"
        else:
            error_previo = (
                f"La query no contiene la propiedad esperada '{item['propiedad_esperada']}' "
                f"o el ID '{id_entidad}', o el sujeto/objeto están invertidos."
            )
        if intento == 0:
            print(f"  [WARN] Zero-Shot fallido. Reflexionando...")

    if not resultado["exito_sparql_final"]:
        print(f"  [FAIL] SPARQL. Esperaba '{item['propiedad_esperada']}' tras {max_intentos} intentos.")
        print(f"         Último SPARQL:\n{query_limpia}")
        resultado["tiempo"] = time.time() - start
        return resultado

    if "respuesta_esperada_contiene" in item and resultados_db:
        valores = [list(fila.values())[0]["value"] for fila in resultados_db]
        dato_traducido = traducir_ids(valores)
        resultado["dato_obtenido"] = dato_traducido

        es_correcto = verificar_respuesta(dato_traducido, item["respuesta_esperada_contiene"])
        resultado["exito_respuesta"] = es_correcto

        if es_correcto:
            print(f"  [OK]   Respuesta verificada: '{dato_traducido[:80]}'")
        else:
            print(f"  [FAIL] Respuesta incorrecta.")
            print(f"         Obtuvo:   '{dato_traducido[:80]}'")
            print(f"         Esperaba contener alguno de: {item['respuesta_esperada_contiene']}")
    else:
        print(f"  [INFO] Sin ground truth de respuesta para esta pregunta.")

    resultado["tiempo"] = time.time() - start
    return resultado


def imprimir_resumen(modelo: str, resultados: list[dict], total: int):
    preguntas_con_gt = [r for r in resultados if r["exito_respuesta"] is not None]

    exitos_entidad      = sum(1 for r in resultados if r["exito_entidad"])
    exitos_zs           = sum(1 for r in resultados if r["exito_sparql_zero_shot"])
    exitos_sparql_final = sum(1 for r in resultados if r["exito_sparql_final"])
    exitos_respuesta    = sum(1 for r in preguntas_con_gt if r["exito_respuesta"])
    tiempo_total        = sum(r["tiempo"] for r in resultados)
    tiempo_medio        = tiempo_total / total if total > 0 else 0

    n_gt = len(preguntas_con_gt)

    print(f"\n{'='*55}")
    print(f"  RESULTADOS — Modelo: {modelo}")
    print(f"{'='*55}")
    print(f"  Preguntas evaluadas:        {total}")
    print(f"  ── Fase 1 (Entidad) ─────────────────────────────────")
    print(f"  Precisión extracción:       {exitos_entidad}/{total}  ({exitos_entidad/total*100:.1f}%)")
    print(f"  ── Fase 2 (SPARQL) ──────────────────────────────────")
    print(f"  Precisión Zero-Shot:        {exitos_zs}/{total}  ({exitos_zs/total*100:.1f}%)")
    print(f"  Precisión con Reflexión:    {exitos_sparql_final}/{total}  ({exitos_sparql_final/total*100:.1f}%)")
    mejora = (exitos_sparql_final - exitos_zs) / total * 100
    print(f"  Mejora por reflexión:       +{mejora:.1f}%")
    print(f"  ── Fase 3 (Respuesta real) ──────────────────────────")
    if n_gt > 0:
        print(f"  Preguntas con ground truth: {n_gt}/{total}")
        print(f"  Precisión respuesta final:  {exitos_respuesta}/{n_gt}  ({exitos_respuesta/n_gt*100:.1f}%)")
    else:
        print(f"  Sin ground truth en el dataset (añade 'respuesta_esperada_contiene').")
    print(f"  ── Tiempo ───────────────────────────────────────────")
    print(f"  Tiempo total:               {tiempo_total:.2f}s")
    print(f"  Tiempo medio por pregunta:  {tiempo_medio:.2f}s")
    print(f"{'='*55}")

    # Detalle de fallos para revisión rápida
    fallos = [r for r in resultados if not r["exito_sparql_final"] or r["exito_respuesta"] is False]
    if fallos:
        print(f"\n  PREGUNTAS FALLIDAS ({len(fallos)}):")
        for r in fallos:
            motivo = []
            if not r["exito_entidad"]:
                motivo.append(f"entidad (obtuvo '{r['entidad_obtenida']}')")
            elif r["error"]:
                motivo.append(r["error"])
            elif not r["exito_sparql_final"]:
                motivo.append("SPARQL no generado correctamente")
            elif r["exito_respuesta"] is False:
                motivo.append(f"respuesta incorrecta (obtuvo '{(r['dato_obtenido'] or '')[:60]}')")
            print(f"  #{r['id']:>3} — {r['pregunta'][:55]}")
            print(f"         Motivo: {', '.join(motivo)}")
        print()

    return {
        "acc_entidad":       exitos_entidad / total * 100,
        "acc_sparql_zs":     exitos_zs / total * 100,
        "acc_sparql_final":  exitos_sparql_final / total * 100,
        "acc_respuesta":     (exitos_respuesta / n_gt * 100) if n_gt > 0 else None,
        "tiempo_total":      tiempo_total,
        "tiempo_medio":      tiempo_medio,
    }


def evaluar_sistema():
    print("Iniciando Evaluación Automática del Sistema (TFG)...\n")

    try:
        with open("dataset_evaluacion.json", "r", encoding="utf-8") as f:
            dataset = json.load(f)
    except FileNotFoundError:
        print("Error: no se encontró 'dataset_evaluacion.json'.")
        print("Estructura esperada de cada entrada:")
        print(json.dumps({
            "id": 1,
            "pregunta": "¿Quién dirigió Inception?",
            "entidad_esperada": "Inception",
            "propiedad_esperada": "P57",
            "respuesta_esperada_contiene": ["Christopher Nolan", "Nolan"]
        }, indent=2, ensure_ascii=False))
        return

    total = len(dataset)
    print(f"Dataset cargado: {total} preguntas.\n")

    # Selección del modelo
    if len(sys.argv) > 1:
        entrada = sys.argv[1]
    else:
        print("Modelos disponibles: llama3, llama3.2:1b, mistral, gemma2:9b, gemma2:2b, deepseek-r1:8b")
        print("Puedes escribir varios modelos separados por comas, o escribir 'todos' para evaluarlos de golpe.")
        entrada = input("Modelos a evaluar (Enter = llama3): ").strip()
        
    if not entrada:
        modelos = ["llama3"]
    elif entrada.lower() == "todos":
        modelos = ["llama3", "llama3.2:1b", "mistral", "gemma2:9b", "gemma2:2b", "deepseek-r1:8b"]
    else:
        modelos = [m.strip() for m in entrada.split(",") if m.strip()]

    resumen_global = {}

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

    for modelo in modelos:
        print(f"\n{'='*55}")
        print(f"  Evaluando modelo: {modelo}")
        print(f"{'='*55}\n")

        resultados_modelo = []

        for item in dataset:
            print(f"── Pregunta #{item['id']}: \"{item['pregunta']}\"")
            
            future = executor.submit(evaluar_pregunta, item, modelo)
            try:
                # Límite estricto de 200 segundos por pregunta
                resultado = future.result(timeout=200)
            except concurrent.futures.TimeoutError:
                print(f"  [TIMEOUT] El modelo se quedó bloqueado más de 200 segundos. Saltando a la siguiente...")
                resultado = {
                    "id": item["id"],
                    "pregunta": item["pregunta"],
                    "exito_entidad": False,
                    "entidad_obtenida": None,
                    "id_wikidata": None,
                    "exito_sparql_zero_shot": False,
                    "exito_sparql_final": False,
                    "intentos_usados": 0,
                    "exito_respuesta": False,
                    "dato_obtenido": None,
                    "ultimo_sparql": "",
                    "tiempo": 200.0,
                    "error": "Timeout (200s)"
                }
            
            resultados_modelo.append(resultado)
            print(f"  [TIEMPO] {resultado['tiempo']:.2f}s")
            print()
            time.sleep(0.5)

        metricas = imprimir_resumen(modelo, resultados_modelo, total)
        resumen_global[modelo] = metricas

    if len(resumen_global) > 1:
        print(f"\n{'='*55}")
        print("  COMPARATIVA ENTRE MODELOS")
        print(f"{'='*55}")
        cabecera = f"{'Modelo':<20} {'Entidad':>8} {'ZS':>7} {'Reflex':>8} {'Respuesta':>10} {'t/preg':>7}"
        print(cabecera)
        print("-" * len(cabecera))
        for mod, m in resumen_global.items():
            resp_str = f"{m['acc_respuesta']:.1f}%" if m['acc_respuesta'] is not None else "  N/A"
            print(
                f"{mod:<20} "
                f"{m['acc_entidad']:>7.1f}% "
                f"{m['acc_sparql_zs']:>6.1f}% "
                f"{m['acc_sparql_final']:>7.1f}% "
                f"{resp_str:>10} "
                f"{m['tiempo_medio']:>6.1f}s"
            )


if __name__ == "__main__":
    evaluar_sistema()