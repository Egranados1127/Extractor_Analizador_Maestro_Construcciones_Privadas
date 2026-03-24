import os
import time
from pathlib import Path
from dashboard import get_text_ocr, extract_data_ai, save_to_db, init_db
import scraper_itagui
import scraper_rionegro

def main():
    print("Iniciando scraping y extracción automática...", flush=True)
    init_db()
    
    # 1. Scraping pages
    print("\n--- PASO 1: Descargando de Itagüí 1 ---", flush=True)
    try:
        count1 = scraper_itagui.scrape_itagui()
    except Exception as e:
        print(f"Error en Itagüí 1: {e}")
        count1 = 0
        
    print("\n--- PASO 2: Descargando de Curaduría 1 Rionegro ---", flush=True)
    # try:
    #     count3 = scraper_rionegro.scrape_rionegro()
    # except Exception as e:
    #     print(f"Error en Rionegro 1: {e}")
    #     count3 = 0


    count1 = count2 = count3 = 0
    print(f"\nDescarga finalizada. PDF nuevos descargados: Itagüí1={count1}, Itagüí2={count2}, Rionegro1={count3}", flush=True)
    
    # 2. Extract Data
    base_dir = Path.cwd()
    folders = [
        base_dir / "Descargas" / "Itagui",
        base_dir / "Descargas" / "Itagui_2",
        # base_dir / "Descargas" / "Rionegro_1"
    ]
    
    files_to_process = []
    
    for folder in folders:
        if folder.exists():
            for f in os.listdir(folder):
                if f.lower().endswith('.pdf'):
                    files_to_process.append({
                        "name": f,
                        "path": folder / f
                    })
    
    import sqlite3
    try:
        conn = sqlite3.connect('master_construcciones.db')
        c = conn.cursor()
        archivos_pendientes = []
        for fi in files_to_process:
            c.execute("SELECT 1 FROM construcciones WHERE archivo = ?", (fi['name'],))
            if c.fetchone() is None:
                archivos_pendientes.append(fi)
        conn.close()
        
        saltados = len(files_to_process) - len(archivos_pendientes)
        if saltados > 0:
            print(f"⏭️ Inteligencia local: Se saltaron {saltados} archivos PDF que ya existían en BD.", flush=True)
            
        files_to_process = archivos_pendientes
    except Exception as e:
        print(f"Error filtrando base de datos pre-ejecución: {e}")

    print(f"\n--- PASO 3: Procesando {len(files_to_process)} PDFs locales NUEVOS con IA (Gemini) ---", flush=True)
    
    nuevos_registros = 0
    for i, file_info in enumerate(files_to_process):
        print(f"Procesando {i+1}/{len(files_to_process)}: {file_info['name']}...", flush=True)
        try:
            with open(file_info['path'], "rb") as f:
                file_bytes = f.read()
                
            txt = get_text_ocr(file_bytes)
            data = extract_data_ai(txt, file_info['name'])
            
            if data:
                data['archivo'] = file_info['name'] # Garantizar identificar el origen
                
                # Forzar municipio si la IA no lo detectó
                if not data.get('municipio'):
                    if 'rionegro' in file_info['name'].lower():
                        data['municipio'] = 'RIONEGRO'
                    elif 'itagui' in file_info['name'].lower():
                        data['municipio'] = 'ITAGÜÍ'
                
                if save_to_db(data):
                    nuevos_registros += 1
                    print(f"  [+] Guardado en DB: {data.get('resolucion', 'N/A')} - {data.get('municipio', 'N/A')} - {data.get('area_m2', 0)}m2", flush=True)
                else:
                    print(f"  [!] Ya existía en DB o falta dato clave al insertar.", flush=True)
            else:
                print(f"  [x] La IA no retornó datos o hubo error parseando el JSON", flush=True)
                
            # Pequeño retardo para no saturar la API de Gemini
            time.sleep(1)
            
        except Exception as e:
            print(f"  [ERROR] Fallo procesando {file_info['name']}: {e}", flush=True)

    print(f"\n=======================================================", flush=True)
    print(f" TERMINADO. Insertados {nuevos_registros} registros nuevos a la BD.")
    print(f" Puedes abrir el Dashboard y ver los datos consolidados.")
    print(f"=======================================================", flush=True)

if __name__ == '__main__':
    main()
