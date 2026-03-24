import streamlit as st
import pandas as pd
import os
import fitz
import pytesseract
from PIL import Image
import google.generativeai as genai
import json
import time
import plotly.express as px
from pathlib import Path
from dotenv import load_dotenv
import sqlite3
from geopy.geocoders import Nominatim, ArcGIS
import folium
from streamlit_folium import st_folium
import base64
import requests
import unicodedata

# Configuración de la Base de Datos Local y Nube
DB_PATH = "master_construcciones.db"
SUPABASE_URL = "https://oubqiodpjhkdrpeukvag.supabase.co"
SUPABASE_KEY = "sb_secret_GUCb7gIZQguts5VjPsxeww_73QJsQo4"
BUCKET_NAME = "construcciones"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Crear tabla si no existe
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS construcciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resolucion TEXT,
            municipio TEXT,
            direccion TEXT,
            propietario TEXT,
            area_m2 REAL,
            niveles INTEGER,
            tipo TEXT,
            fecha TEXT,
            archivo TEXT UNIQUE, -- UNIQUE para evitar duplicar el mismo PDF
            fecha_extraccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    
    # Añadir lat y lon si no existen en versiones previas
    cursor.execute("PRAGMA table_info(construcciones)")
    cols = [col[1] for col in cursor.fetchall()]
    if 'lat' not in cols:
        cursor.execute("ALTER TABLE construcciones ADD COLUMN lat REAL")
        cursor.execute("ALTER TABLE construcciones ADD COLUMN lon REAL")
    conn.commit()
    conn.close()

# Inicializar BD al arrancar
init_db()

def geocode_missing_coordinates():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Buscar aquellos que no tienen coords o que fallaron antes (lat=0)
    cursor.execute("SELECT id, direccion, municipio FROM construcciones WHERE lat IS NULL OR lon IS NULL OR lat = 0")
    rows = cursor.fetchall()
    
    if not rows:
        conn.close()
        return 0
        
    # ArcGIS es mucho más tolerante con direcciones irregulares/latinas que Nominatim
    geolocator = ArcGIS(user_agent="visor_construcciones_premium_co")
    count = 0
    for row in rows:
        row_id, direccion, municipio = row
        
        # Limpieza básica para Colombia
        dir_clean = str(direccion).replace("LOTE", "").replace("MANZANA", "MZ").strip()
        query = f"{dir_clean}, {municipio}, Antioquia, Colombia"
        
        try:
            time.sleep(0.5)
            location = geolocator.geocode(query, timeout=10)
            if location:
                # Si las coordenadas caen exactamente en el centro cero o fuera de colombia omitir
                if location.latitude != 0:
                    cursor.execute("UPDATE construcciones SET lat = ?, lon = ? WHERE id = ?", (location.latitude, location.longitude, row_id))
                    count += 1
                else:
                    cursor.execute("UPDATE construcciones SET lat = ?, lon = ? WHERE id = ?", (0, 0, row_id))
            else: 
                cursor.execute("UPDATE construcciones SET lat = ?, lon = ? WHERE id = ?", (0, 0, row_id))
            conn.commit()
        except Exception as e:
            # En caso de error, continuar con las demas
            continue
            
    conn.close()
    return count

def save_to_db(data):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Insertar o ignorar si ya existe el archivo (por el UNIQUE)
        cursor.execute('''
            INSERT OR IGNORE INTO construcciones 
            (resolucion, municipio, direccion, propietario, area_m2, niveles, tipo, fecha, archivo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('resolucion', ''),
            data.get('municipio', ''),
            data.get('direccion', ''),
            data.get('propietario', ''),
            data.get('area_m2', 0.0),
            data.get('niveles', 0),
            data.get('tipo', ''),
            data.get('fecha', ''),
            data.get('archivo', '')
        ))
        inserted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return inserted
    except Exception as e:
        st.error(f"Error guardando en BD: {e}")
        return False

def load_from_db():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM construcciones", conn)
    conn.close()
    return df

# Configuración de la App - LOOK PREMIUM
st.set_page_config(page_title="Extractor Premium AI - Construcciones Privadas", layout="wide", page_icon="🏗️")

# Estilos personalizados CSS Global
st.markdown("""
<style>
    /* Fondo azul más oscuro y corporativo para Main y Sidebar */
    .stApp > header { background-color: transparent !important; }
    .stApp, .stAppViewContainer { background-color: #081a30 !important; }
    [data-testid="stSidebar"] { background-color: #051424 !important; }
    
    /* Textos en contenedores principales */
    h1, h2, h3, h4, h5, h6, .stMarkdown, label { color: white !important; }
    
    /* Arreglo para el File Uploader */
    [data-testid="stFileUploadDropzone"] { background-color: rgba(255,255,255,0.05) !important; border: 1px dashed rgba(255,255,255,0.3) !important; border-radius: 10px; }
    [data-testid="stFileUploadDropzone"] * { color: white !important; }
    
    /* Arreglo del Menú Desplegable (Selectbox) para que sea oscuro y no se confunda con la tabla */
    [data-baseweb="select"] > div { background-color: #102a43 !important; border: 1px solid #1e4b7a !important; color: white !important; }
    [data-baseweb="popover"] > div, ul[data-baseweb="menu"] { background-color: #102a43 !important; }
    ul[data-baseweb="menu"] li { color: white !important; border-bottom: 1px solid rgba(255,255,255,0.05); }
    ul[data-baseweb="menu"] li:hover { background-color: #1e4b7a !important; }
    
    /* Botones Premium Translúcidos */
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background: rgba(255,255,255,0.1) !important; color: white !important; border: 1px solid rgba(255,255,255,0.3) !important; font-weight: bold; backdrop-filter: blur(4px); transition: all 0.2s; }
    .stButton>button:hover { background: rgba(255,255,255,0.2) !important; border-color: white !important; transform: translateY(-2px); }
    
    /* Métricas Streamlit estándar */
    .stMetric { background-color: rgba(255,255,255,0.05); padding: 15px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.1); backdrop-filter: blur(5px); }
</style>
""", unsafe_allow_html=True)

# Cargar API
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# Lógica de Extracción (Basada en motor_georef.py)
def get_text_ocr(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for i in range(min(4, len(doc))): # Leemos las primeras 4 páginas importantes
        p = doc[i]
        t = p.get_text()
        if not t.strip():
            pix = p.get_pixmap(dpi=150)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            t = pytesseract.image_to_string(img, lang='spa')
        text += t + "\n"
    return text

def extract_data_ai(text, filename):
    import re
    model = genai.GenerativeModel("models/gemini-2.5-flash")
    prompt = f"""Eres un experto analizando documentos legales de Curadurías y Licencias de Construcción en Colombia.
    Extrae la siguiente información del texto y devuélvela ÚNICAMENTE en formato JSON válido, sin preámbulos ni markdown adicional.
    Si un dato no existe en el texto, el valor debe ser null. NO uses los textos de ejemplo como valores.
    
    Plantilla JSON a devolver:
    {{
      "resolucion": "Número de resolución, radicado o expediente",
      "municipio": "Nombre del municipio (ej: Rionegro, Itagüí)",
      "direccion": "Dirección completa del predio o lote",
      "propietario": "Nombre completo del titular, titularidad o propietario",
      "area_m2": (Número real, área a construir o área total de los metros cuadrados. Ej: 250.5),
      "niveles": (Número entero, cantidad de pisos o niveles. Ej: 2),
      "tipo": "Uso o modalidad de la licencia (Ej: Vivienda, Comercial, Obra Nueva, Industrial)",
      "fecha": "Fecha principal de expedición (formato dd/mm/aaaa)"
    }}
    
    TEXTO DEL DOCUMENTO:
    {text[:20000]}"""
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        raw = response.text.replace("```json", "").replace("```", "").strip()
        # Intentar extraer solo el bloque JSON por si acaso
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
             raw = match.group(0)
        return json.loads(raw)
    except Exception as e:
        print(f"Error parseando JSON de {filename}: {e}", flush=True)
        return None

import scraper_itagui
import scraper_snr
import scraper_rionegro
# --- UI PRINCIPAL ---
col_logo, col_title = st.columns([1, 4])
with col_logo:
    try:
        st.image("logo.png", use_container_width=True)
    except:
        st.write("🏢")
with col_title:
    st.markdown("<h1 style='margin-bottom: 0px; padding-bottom: 0;'>J&E Soluciones</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='margin-top: 5px; color: #bfdbfe !important;'>Extractor y Analizador Maestro de Construcciones Privadas</h4>", unsafe_allow_html=True)
st.markdown("---")

# Sidebar para carga
with st.sidebar:
    st.header("🗂️ Origen de Datos")
    
    # NUEVA FUNCIONALIDAD: Captura Directa
    st.subheader("🌐 Captura On-line")
    
    st.caption("📅 Periodo de Extracción")
    selected_period = st.selectbox("Mes de Resolución:", ["2026-03", "2026-02", "2026-01", "2025-12", "2025-11", "2025-10", "2025-09", "2025-08", "2025-07"])
    year_suffix = selected_period[2:4] # De "2026-03" -> "26"
    
    col_cap1, col_cap2 = st.columns(2)
    with col_cap1:
        if st.button("📥 ITAGÜÍ 1"):
            with st.spinner(f"Curaduría 1 ({selected_period})..."):
                count = scraper_itagui.scrape_itagui()
                st.success(f"Itagüí 1: {count} PDF")
                
    with col_cap2:
        if st.button("📥 BELLO C2"):
            with st.spinner(f"API SNR ({selected_period})..."):
                count = scraper_snr.scrape_snr([year_suffix])
                st.success(f"Bello C2: {count} PDF")
        
        if st.button("📥 RIONEGRO C1"):
            with st.spinner("Scraping Curaduría 1 Rionegro (Todas las fechas)..."):
                count = scraper_rionegro.scrape_rionegro()
                st.success(f"Rionegro 1: {count} PDF nuevos")
    
    st.divider()
    
    # Opción: Carpeta Local IA
    st.subheader("📁 Procesamiento IA Offline")
    default_path = str(Path.cwd() / "Tipos Pdf")
    
    folder_option = st.selectbox("Carpeta de Análisis:", ["Tipos Pdf", "Otra ruta específica..."])
    
    final_folders = []
    if folder_option == "Tipos Pdf":
        final_folders = [default_path]
    else:
        custom_folder = st.text_input("📁 Ingrese ruta absoluta:", value=default_path)
        final_folders = [custom_folder]

    scan_folder = st.button("🔍 ESCANEAR CARPETA(S)")
    
    st.divider()
    
    # Opción 2: Subir archivos (Para casos puntuales)
    uploaded_files = st.file_uploader("📥 O subir archivos sueltos (PDF)", accept_multiple_files=True, type=['pdf'])
    process_btn = st.button("🚀 EJECUTAR EXTRACCIÓN")
    
    st.divider()
    st.info("Configurado para detectar Resoluciones 2025/2026 y georreferenciación de obra.")

# Columnas para resumen (Dashboard)
col1, col2, col3, col4 = st.columns(4)

# Lógica de Ejecución
files_to_process = []

if scan_folder:
    total_found = 0
    for folder in final_folders:
        if os.path.exists(folder):
            files = [f for f in os.listdir(folder) if f.lower().endswith('.pdf')]
            for f in files:
                files_to_process.append({"name": f, "path": os.path.join(folder, f), "type": "local"})
                total_found += 1
        else:
            st.sidebar.warning(f"Ruta no encontrada: {folder}")
    
    if total_found > 0:
        st.sidebar.success(f"Total: {total_found} archivos encontrados.")
    else:
        st.sidebar.error("No se encontraron archivos PDF.")

if uploaded_files:
    for f in uploaded_files:
        files_to_process.append({"name": f.name, "content": f.read(), "type": "upload"})

if (process_btn or scan_folder) and files_to_process:
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    start_time = time.time()
    
    for i, file_info in enumerate(files_to_process):
        status_text.text(f"Procesando: {file_info['name']} ({i+1}/{len(files_to_process)})")
        
        try:
            if file_info['type'] == "local":
                with open(file_info['path'], "rb") as f:
                    file_bytes = f.read()
            else:
                file_bytes = file_info['content']
                
            txt = get_text_ocr(file_bytes)
            data = extract_data_ai(txt, file_info['name'])
            
            if data:
                data['archivo'] = file_info['name']
                results.append(data)
        except Exception as e:
            st.error(f"Error procesando {file_info['name']}: {e}")
        
        progress_bar.progress((i + 1) / len(files_to_process))
        
    end_time = time.time()
    st.success(f"✅ ¡Extracción completada en {round(end_time - start_time, 1)} segundos!")
    
    # Guardar en la Base de Datos Local
    nuevos_registros = 0
    for item in results:
        if save_to_db(item):
            nuevos_registros += 1
            
    if nuevos_registros > 0:
        st.success(f"💾 Se han guardado {nuevos_registros} registros NUEVOS en la base de datos maestra.")
    else:
        st.info("ℹ️ No se guardaron registros nuevos (todos los PDFs procesados ya existían en la BD).")

# --- CARGAR DATOS DESDE LA BASE DE DATOS MAESTRA ---
# Siempre leemos de la base de datos para mostrar el dashboard real
df = load_from_db()

# Mostrar Dashboard si hay datos
if not df.empty:
    
    # 0. NORMALIZACIÓN SEMÁNTICA DE MUNICIPIOS
    # Convertimos todo a mayúsculas para unificar base
    df['municipio'] = df['municipio'].str.upper()
    # Limpiamos todas las variaciones de ortografía / IA confusiones para Itagüí
    df['municipio'] = df['municipio'].replace(
        ['ITAGUI', 'ITAGUÍ', 'ITAGÜI', 'ITAGÚI', 'ITAGÚÍ', 'ITÁGUI'], 
        'ITAGÜÍ'
    )
    # Ejemplo de otras a futuro: df['municipio'] = df['municipio'].replace(['MEDELLIN'], 'MEDELLÍN')
    
    # 1. FORZAR ORDENAMIENTO POR ÁREA (Mayor a Menor) Y LIMPIAR ÍNDICES
    df['area_m2'] = pd.to_numeric(df['area_m2'], errors='coerce').fillna(0)
    df = df.sort_values(by="area_m2", ascending=False).reset_index(drop=True)
    
    # CSS Ultra Premium para Sidebar, Tabs y Cards enfocado en Layout Oscuro-Azul
    st.markdown("""
    <style>
        .stTabs [data-baseweb="tab-list"] { gap: 10px; margin-bottom: 20px; }
        .stTabs [data-baseweb="tab"] { background-color: transparent !important; border: 1px solid rgba(255,255,255,0.2) !important; padding: 15px 25px; font-weight: 600; font-size: 16px; border-radius: 5px 5px 0 0; color: #cbd5e1 !important; }
        .stTabs [aria-selected="true"] { background-color: rgba(255,255,255,0.15) !important; border-bottom: 3px solid #60a5fa !important; color: white !important; }
        
        .metric-card { background: rgba(255,255,255,0.1); border-left: 6px solid #60a5fa; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); transition: transform 0.2s; backdrop-filter: blur(5px); }
        .metric-card:hover { transform: translateY(-3px); }
        .metric-label { font-size: 14px; color: #bfdbfe; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; }
        .metric-value { font-size: 32px; color: white; font-weight: 900; margin-top: 8px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    </style>
    """, unsafe_allow_html=True)
    
    # Evaluar si hay coordenadas pendientes
    if 'lat' in df.columns and df['lat'].isnull().any():
        st.info("🌎 Existen nuevos registros sin coordenadas satelitales.")
        if st.button("🗺️ Generar Geoposición de Obras Nuevas"):
            with st.spinner("Conectando con satélites para trazar ubicaciones (puede tardar un poco)..."):
                n = geocode_missing_coordinates()
                st.success(f"¡Se han ubicado {n} obras nuevas en el radar!")
                time.sleep(2)
                st.rerun()

    # Layout Premium - Métricas como Cards Reales (usando HTML/CSS inline)
    html_metrics = f"""
    <div style="display: flex; gap: 20px; margin-bottom: 30px;">
        <div style="flex: 1;" class="metric-card">
            <div class="metric-label">Obras Extraídas</div>
            <div class="metric-value">{len(df)}</div>
        </div>
        <div style="flex: 1;" class="metric-card">
            <div class="metric-label">Total Área (m²)</div>
            <div class="metric-value">{df['area_m2'].sum():,.0f}</div>
        </div>
        <div style="flex: 1;" class="metric-card">
            <div class="metric-label">Municipios Analizados</div>
            <div class="metric-value">{df['municipio'].nunique()}</div>
        </div>
    </div>
    """
    st.markdown(html_metrics, unsafe_allow_html=True)
    
    # Layout de Pestañas
    tab1, tab2, tab3 = st.tabs(["📋 Base de Datos y Documentos", "🗺️ Mapa Satelital Espacial", "📊 Analíticas Visuales"])
    
    with tab1:
        st.markdown("### 🗃️ Navegador Principal")
        st.markdown("<span style='color: #666; font-size: 15px;'>Para auditar la información, simplemente **haz clic en una fila** de la tabla de la izquierda y el documento soporte oficial se desplegará instantáneamente en el panel derecho.</span>", unsafe_allow_html=True)
        st.markdown("---")
        
        # Split layout para ver Tabla y PDF a la vez (Pantalla Dividida)
        view_col1, view_col2 = st.columns([1.5, 1], gap="large")
        
        with view_col1:
            # 2. LOGICA DE FILTRO POR FECHA ORDENADA CRONOLÓGICAMENTE
            # Convirtiendo fecha local a formato DateTime real de pandas
            fechas_reales = pd.to_datetime(df['fecha'], errors='coerce', dayfirst=True)
            # Usando to_period para extraer Año-Mes numérico ordenable (Ej: 2026-06)
            df['periodo_dt'] = fechas_reales.dt.to_period('M')
            # Cadena estética (Ej: '06-2026') 
            df['Mes_Periodo'] = df['periodo_dt'].dt.strftime('%m-%Y').fillna('Indeterminado')
            
            # Obtener periodos únicos reales ordenados matemáticamente hacia atrás
            periodos_ordenados = sorted([p for p in df['periodo_dt'].unique() if not pd.isna(p)], reverse=True)
            opciones_periodo = ['Todos los periodos'] + [p.strftime('%m-%Y') for p in periodos_ordenados]
            if 'Indeterminado' in df['Mes_Periodo'].values:
                opciones_periodo.append('Indeterminado')
            
            f_col1, f_col2 = st.columns(2)
            
            with f_col1:
                filtro_mes = st.selectbox("📅 Filtro Cronológico (Mes de Resolución):", opciones_periodo)
            
            with f_col2:
                opciones_muni = ['Todos los municipios'] + sorted(list(df['municipio'].dropna().unique()))
                filtro_muni = st.selectbox("📍 Filtrar por Municipio:", opciones_muni)
            
            # Condicional en cadena (Aplicando todos los filtros que no sean "Todos...")
            df_mostrar = df.copy()
            if filtro_mes != 'Todos los periodos':
                df_mostrar = df_mostrar[df_mostrar['Mes_Periodo'] == filtro_mes]
                
            if filtro_muni != 'Todos los municipios':
                df_mostrar = df_mostrar[df_mostrar['municipio'] == filtro_muni]
            
            # Mostramos dataframe filtrado y sin columnas técnicas (periodo_dt y Mes_Periodo ocultas)
            event = st.dataframe(
                df_mostrar.drop(columns=['id', 'fecha_extraccion', 'Mes_Periodo', 'periodo_dt'], errors='ignore'), 
                use_container_width=True,
                on_select="rerun",
                selection_mode="single-row",
                hide_index=True
            )
            csv = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button("📥 Descargar Reporte Consolidado (CSV)", csv, "master_construcciones.csv", "text/csv")
            
        with view_col2:
            st.markdown("#### 🔍 Visor de Soporte Legal")
            selected_pdf = None
            if getattr(event, "selection", None) is not None and len(event.selection.rows) > 0:
                row_idx = event.selection.rows[0]
                # ATENCION: Es vital usar df_mostrar para que el índice coincida con lo mostrado!
                selected_pdf = df_mostrar.iloc[row_idx]['archivo']
                
            if selected_pdf:
                st.markdown(f"📄 **Soporte Legal Activo:** `{selected_pdf}`")
                pdf_path = None
                search_dirs = [Path.cwd() / "Descargas" / "Itagui", Path.cwd() / "Descargas" / "Bello", Path.cwd() / "Descargas" / "Rionegro_1", Path.cwd() / "Tipos Pdf", Path.cwd() / "Descargas" / "Medellin_1"]
                for d in search_dirs:
                    if (d / selected_pdf).exists():
                        pdf_path = d / selected_pdf
                        break
                        
                if pdf_path:
                    with open(pdf_path, "rb") as f:
                        pdf_bytes_down = f.read()
                else:
                    # Si no se encuentra localmente, procedemos a Cloud Supabase
                    with st.spinner("Conectando con Supabase Cloud Storage para descargar..."):
                        clean_name = unicodedata.normalize('NFKD', selected_pdf).encode('ASCII', 'ignore').decode('utf-8')
                        url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{clean_name}"
                        try:
                            # Intento público primero, si falla intenta con headers autenticados
                            res = requests.get(url)
                            if res.status_code != 200:
                                url_auth = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{clean_name}"
                                headers = {"Authorization": f"Bearer {SUPABASE_KEY}", "apikey": SUPABASE_KEY}
                                res = requests.get(url_auth, headers=headers)
                            
                            if res.status_code == 200:
                                pdf_bytes_down = res.content
                            else:
                                pdf_bytes_down = None
                        except:
                            pdf_bytes_down = None

                if pdf_bytes_down:
                    st.download_button(label="📥 Descargar PDF Analizado (Local/Nube)", data=pdf_bytes_down, file_name=selected_pdf, mime="application/pdf")
                    
                    with st.container(height=600):
                        try:
                            # Renderizado confiable convirtiendo páginas a imágenes
                            doc = fitz.open(stream=pdf_bytes_down, filetype="pdf")
                            for page_num in range(len(doc)):
                                page = doc.load_page(page_num)
                                pix = page.get_pixmap(dpi=150)
                                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                                st.image(img, use_container_width=True, caption=f"Página {page_num + 1} de {len(doc)}")
                            doc.close()
                        except Exception as e:
                            st.warning(f"No se pudo cargar la previsualización: {e}")
                else:
                    st.error("❌ El archivo local fue movido y tampoco pudo ser ubicado en Supabase Cloud.")
            else:
                st.info("👈 Selecciona cualquier fila en la tabla de la izquierda para abrir el documento instantáneamente aquí.")

    with tab2:
        st.markdown("### 🗺️ Visualización Estratégica Espacial")
        if 'lat' in df.columns and 'lon' in df.columns:
            df_map = df.dropna(subset=['lat', 'lon'])
            # Filtrar coordenadas nulas / inválidas
            df_map = df_map[(df_map['lat'] != 0) & (df_map['lon'] != 0)]
            
            if not df_map.empty:
                m = folium.Map(location=[df_map['lat'].mean(), df_map['lon'].mean()], zoom_start=14, tiles="CartoDB positron")
                for idx, row in df_map.iterrows():
                    html_popup = f"""
                    <div style='font-family: Arial; font-size: 13px; min-width: 200px;'>
                        <div style='background-color:#004e92; color:white; padding:5px; border-radius:3px; margin-bottom:5px; font-weight:bold;'>
                            Resolución {row['resolucion']}
                        </div>
                        <b>Uso:</b> {row['tipo']}<br>
                        <b>Área Obra:</b> {row['area_m2']} m²<br>
                        <b>Dueño:</b> {row['propietario']}
                    </div>
                    """
                    folium.Marker(
                        [row['lat'], row['lon']],
                        popup=folium.Popup(html_popup, max_width=300),
                        tooltip=f"Hacer clic para ver detalles de la obra en: {row['direccion']}",
                        icon=folium.Icon(color="darkblue", icon="info-sign")
                    ).add_to(m)
                st_folium(m, width="100%", height=600, returned_objects=[])
            else:
                st.warning("Presiona el botón 'Generar Geoposición' (Arriba, si aparece) para conectar las obras con el satélite.")
        else:
            st.info("Las coordenadas aún no están disponibles o no se han calculado.")

    with tab3:
        st.markdown("### 📊 Analítica del Negocio Inmobiliario")
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(
                df, x="municipio", y="area_m2", color="municipio", 
                title="Metros Cuadrados Proyectados por Municipio", 
                template="plotly_dark", text_auto=".2s"
            )
            fig.update_layout(
                title_font_size=18, title_font_weight="bold", title_font_color="white",
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            if 'niveles' in df.columns and not df['niveles'].dropna().empty:
                fig2 = px.pie(
                    df, names="niveles", title="Distribución de Obras por Cantidad de Pisos", 
                    hole=0.45, template="plotly_dark"
                )
                fig2.update_layout(
                    title_font_size=18, title_font_weight="bold", title_font_color="white",
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig2, use_container_width=True)

else:
    # Pantalla Vacía mucho más amigable
    st.info(" 👋 Hola. No hay datos registrados todavía en la Base de Datos Maestra.")
    st.markdown("""
    **Para comenzar, prueba una de estas opciones:**
    1. Usa el panel izquierdo en **"Captura On-line"** para descargar automáticamente desde las Curadurías de Itagüí y luego dale al botón de "Escanear Carpeta(S)".
    2. Sube un archivo PDF manualmente desde el menú lateral y dale a ejecutar.
    """)

