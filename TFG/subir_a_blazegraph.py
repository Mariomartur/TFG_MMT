import requests
import sys
import os

ENDPOINT = "http://localhost:9999/blazegraph/sparql"
FILE_PATH = "datos_cine_limpio.nt"

def main():
    if not os.path.exists(FILE_PATH):
        print(f"Error: No se encuentra el archivo {FILE_PATH}.")
        sys.exit(1)

    tamaño_mb = os.path.getsize(FILE_PATH) / (1024 * 1024)
    print(f"Subiendo {FILE_PATH} ({tamaño_mb:.2f} MB) a Blazegraph...")
    print("Esto puede tardar varios minutos dependiendo del tamaño. No lo canceles...")

    with open(FILE_PATH, "rb") as f:
        headers = {"Content-Type": "text/plain"}
        try:
            # Al pasar el objeto archivo directamente (data=f), 
            # requests hace la subida en streaming (sin reventar la RAM).
            response = requests.post(ENDPOINT, data=f, headers=headers)
            
            if response.status_code == 200:
                print("\n✅ ¡Subida completada con éxito!")
                print("Respuesta de Blazegraph:")
                print(response.text)
            else:
                print(f"\n❌ Error {response.status_code} al subir los datos.")
                print(response.text)
                
        except requests.exceptions.ConnectionError:
            print(f"\n❌ Error de conexión. ¿Está Blazegraph encendido en {ENDPOINT}?")

if __name__ == "__main__":
    main()
