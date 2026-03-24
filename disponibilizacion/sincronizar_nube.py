import os
import requests
import unicodedata

SUPABASE_URL = "https://oubqiodpjhkdrpeukvag.supabase.co"
SUPABASE_KEY = "sb_secret_GUCb7gIZQguts5VjPsxeww_73QJsQo4"
BUCKET_NAME = "construcciones"
FOLDERS_TO_SYNC = ["Descargas", "Tipos Pdf"]

def sync_nube():
    print("☁️ Iniciando Sincronización Inteligente a Supabase...")
    headers_api = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json"
    }
    headers_pdf = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/pdf"
    }
    
    # 1. Obteniendo lista de archivos remotos
    print("🔍 Consultando archivos existentes en la nube...")
    remote_files = set()
    url_list = f"{SUPABASE_URL}/storage/v1/object/list/{BUCKET_NAME}"
    offset = 0
    limit = 1000
    while True:
        payload = {"prefix": "", "limit": limit, "offset": offset, "sortBy": {"column": "name", "order": "asc"}}
        res = requests.post(url_list, headers=headers_api, json=payload)
        if res.status_code == 200:
            objects = res.json()
            if not objects:
                break
            for obj in objects:
                if obj['name'].endswith('.pdf'):
                    # Guardamos el nombre tal como está en la nube (sin acentos)
                    remote_files.add(obj['name'])
            offset += limit
        else:
            print(f"❌ Error consultando nube: {res.text}")
            return
            
    print(f"📦 Archivos en Nube encontrados: {len(remote_files)}")

    # 2. Recolectando locales y filtrando faltantes
    faltantes = []
    ignorados = 0
    for d in FOLDERS_TO_SYNC:
        if os.path.exists(d):
            for root, dirs, files in os.walk(d):
                for f in files:
                    if f.endswith('.pdf'):
                        original_filename = os.path.basename(f)
                        # El nombre que tendrá en supabase:
                        clean_name = unicodedata.normalize('NFKD', original_filename).encode('ASCII', 'ignore').decode('utf-8')
                        if clean_name not in remote_files:
                            faltantes.append((os.path.join(root, f), clean_name))
                        else:
                            ignorados += 1
                            
    print(f"⏭️ {ignorados} archivos detectados como ya existentes. Se ignorarán.")
    print(f"🚀 Iniciando subida de {len(faltantes)} archivos faltantes...")

    # 3. Subiendo solo los faltantes
    subidos = 0
    errores = 0
    for i, (filepath, clean_name) in enumerate(faltantes):
        url_upload = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{clean_name}"
        try:
            with open(filepath, "rb") as f:
                pdf_bytes = f.read()
            res = requests.post(url_upload, headers=headers_pdf, data=pdf_bytes)
            if res.status_code in (200, 201):
                subidos += 1
                print(f"  [{subidos}/{len(faltantes)}] ✅ Subido: {clean_name}")
            else:
                errores += 1
                print(f"  [!] Error {res.status_code} al subir {clean_name}: {res.text}")
        except Exception as e:
            errores += 1
            print(f"  [!] Exception al subir {clean_name}: {e}")

    print("\n==================================================")
    print(f"✅ FINALIZADO. {subidos} documentos NUEVOS subidos exitosamente.")
    if errores > 0:
        print(f"❌ Hubo {errores} errores en la subida.")
    print("==================================================")

if __name__ == "__main__":
    sync_nube()
