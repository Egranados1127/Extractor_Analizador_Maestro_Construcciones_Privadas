import sqlite3
from sodapy import Socrata
import json
import os

# Cargar API de Gemini para la IA
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def analyze_with_ai(desc_batch):
    # Toma un diccionario {id: descripcion} y retorna {id: booleano (Aplica)}
    model = genai.GenerativeModel("models/gemini-2.5-flash")
    prompt = """Eres el analista de negocios de Fiel Ferreteros, distribuidora de materiales de construcción, obra, herramientas, sector eléctrico e infraestructura civil.
Evalúa este lote de procesos públicos de contratación y determina si APLICAMOS (True) para ser el proveedor de materiales o ejecutores, o NO APLICAMOS (False).
Rechaza (False) mantenimientos de computadores, aseo, transporte, servicios legales, alimentación, software, dotación médica, papel, insumos de oficina y eventos.
Acepta (True) todo lo que huela a ladrillo, cable, pintura, focos, pavimento, tubería, madera, acero, herramientas, remodelación locativa, acueductos.

Retorna ÚNICAMENTE JSON válido con formato:
{"ID_PROCESO": true o false}

PROCESOS A EVALUAR:
"""
    
    for proc_id, desc in desc_batch.items():
        prompt += f"ID [{proc_id}]: {desc}\n"
        
    try:
        response = model.generate_content(prompt, generation_config=genai.GenerationConfig(response_mime_type="application/json"))
        raw = response.text.replace("```json", "").replace("```", "").strip()
        import re
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        return json.loads(match.group(0)) if match else {}
    except Exception as e:
        print("Error de IA:", e)
        return {}

def update_obras_publicas():
    # Asegurar conexión local a BD
    conn = sqlite3.connect('master_construcciones.db')
    c = conn.cursor()
    
    # Creación de tabla para SECP / Obras Públicas
    c.execute('''CREATE TABLE IF NOT EXISTS obras_publicas (
                    id_proceso TEXT PRIMARY KEY,
                    entidad TEXT,
                    municipio TEXT,
                    descripcion TEXT,
                    valor_estimado REAL,
                    estado TEXT,
                    fecha_publicacion TEXT,
                    url_proceso TEXT,
                    tag_fiel TEXT DEFAULT 'Analizar'
                )''')
                
    # Filtro local balanceado: Palabras lo suficientemente específicas para no traer basura, 
    # pero genéricas en construcción para atrapar miles de compras menores (mínima cuantía).
    keywords_estrictos = [
        "FERRETER", "ACERO", "LUMINARIA", "ALUMBRADO", "PAVIMENTA",
        "CEMENTO", "TUBERIA", "MAQUINARIA AMARILLA", "TRITURADO", 
        "PINTURA", "CABLES ELECTRICOS", "ILUMINACION", "TRANSFORMADOR",
        "MEJORAMIENTO LOCATIVO", "ADECUACION LOCATIVA", "MANTENIMIENTO DE INFRAESTRUCTURA",
        "MANTENIMIENTO DE LA INFRAESTRUCTURA", "MATERIALES DE CONSTRUCCION",
        "MATERIALES DE FERRETERIA", "HERRAMIENTA MANUAL", "SOLDADURA", "LADRILLO", 
        "INSTALACIONES ELECTRICAS", "CABLEADO", "OBRA CIVIL", "OBRAS CIVILES",
        "ACUEDUCTO Y ALCANTARILLADO", "CERRADURA", "CERRAJERIA", "DOTACION INDUSTRIAL",
        "ELEMENTOS DE PROTECCION PERSONAL", "CUBIERTA", "TECHOS", "CANOAS", "HERRAJES",
        "CONSTRUCCI", "CONSTRUCTIVO", "EDIFICACION"
    ]
    
    # Buscar la fecha más reciente de publicación que ya tengamos en la BD
    c.execute("SELECT MAX(fecha_publicacion) FROM obras_publicas")
    last_date = c.fetchone()[0]
    
    # Si tenemos una última fecha, buscamos todo lo que sea mayor o igual a esa fecha (para atrapar los del mismo día)
    # Si no, caemos en el inicio de 2025 por defecto.
    if last_date:
        # Aseguramos el formato de Socrata (borramos la Z si la tiene o .000)
        safe_date = str(last_date).replace('Z', '')
        full_where = f"fecha_de_publicacion_del >= '{safe_date}' AND departamento_entidad = 'Antioquia'"
    else:
        full_where = "fecha_de_publicacion_del >= '2025-01-01T00:00:00.000' AND departamento_entidad = 'Antioquia'"
    
    try:
        client = Socrata("www.datos.gov.co", None, timeout=60)
        results = client.get("p6dx-8zbt", where=full_where, limit=50000, order="fecha_de_publicacion_del DESC")
        print(f"[*] SECOP retornó {len(results)} procesos (Desde {last_date or '2025/01'}). Filtrando con IA...")
    except Exception as e:
        print(f"Error conectando a SECOP vía Socrata: {e}")
        return 0

    inserted = 0
    batch_desc = {}
    
    for row in results:
        id_proceso = row.get('id_del_proceso', 'UNKNOWN')
        descripcion = row.get('descripci_n_del_procedimiento', '').upper()
        
        # Pre-filtro Semántico Rápido y Limpio
        if not any(kw in descripcion for kw in keywords_estrictos):
            continue
            
        entidad = row.get('entidad', 'Entidad Desconocida')
        municipio = row.get('ciudad_entidad', 'ANTIOQUIA').upper()
        
        valor_str = row.get('precio_base', '0')
        try:
            valor_estimado = float(valor_str)
        except:
            valor_estimado = 0.0
            
        estado = row.get('estado_resumen', row.get('estado_del_procedimiento', 'Desconocido'))
        fecha = row.get('fecha_de_publicacion_del', '')
        
        url_raw = row.get('urlproceso', '')
        url_proceso = url_raw.get('url', '') if isinstance(url_raw, dict) else str(url_raw)
            
        try:
            c.execute('''INSERT OR IGNORE INTO obras_publicas 
                            (id_proceso, entidad, municipio, descripcion, valor_estimado, estado, fecha_publicacion, url_proceso, tag_fiel) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                        (id_proceso, entidad, municipio, descripcion, valor_estimado, estado, fecha, url_proceso, "Pendiente IA"))
            if c.rowcount > 0:
                inserted += 1
                batch_desc[id_proceso] = descripcion
        except Exception as db_e:
            pass

    conn.commit()
    
    # == SEGUNDA PARTE: PROCESAMIENTO INTELIGENTE POR LOTES ==
    pendientes = list(batch_desc.items())
    print(f"--- 🤖 Enviando {len(pendientes)} contratos detectados a los Agentes FIEL de Gemini para filtro final... ---")
    
    batch_size = 50
    for i in range(0, len(pendientes), batch_size):
        chunk = dict(pendientes[i:i+batch_size])
        print(f"Evaluando lote {i} a {i+len(chunk)}...")
        ai_judgments = analyze_with_ai(chunk)
        
        # Procesar sentencia de la IA
        for p_id, aplica in ai_judgments.items():
            final_tag = 'APLICA' if aplica else 'RESTRINGIDO'
            c.execute("UPDATE obras_publicas SET tag_fiel = ? WHERE id_proceso = ?", (final_tag, p_id))
        
        conn.commit()
        import time
        time.sleep(3)  # Respetar rate limit gratuito de Gemini

    conn.close()
    
    print(f"--- 🚀 Finalizado SECOP. {inserted} licitaciones NUEVAS fueron guardadas. ---")
    
    try:
        import shutil
        ruta_origen = 'master_construcciones.db'
        ruta_destino = os.path.join('disponibilizacion', 'master_construcciones.db')
        if os.path.exists(ruta_origen) and os.path.exists('disponibilizacion'):
            shutil.copy2(ruta_origen, ruta_destino)
    except Exception as e:
        pass
        
    return inserted

if __name__ == '__main__':
    update_obras_publicas()
