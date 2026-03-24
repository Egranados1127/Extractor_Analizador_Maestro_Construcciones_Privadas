import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import folium
from streamlit_folium import st_folium
import fitz
from PIL import Image
from pathlib import Path
import base64
import requests
import unicodedata

import os

# Configuración de la Base de Datos Local y Nube
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "master_construcciones.db")
SUPABASE_URL = "https://oubqiodpjhkdrpeukvag.supabase.co"
SUPABASE_KEY = "sb_secret_GUCb7gIZQguts5VjPsxeww_73QJsQo4"
BUCKET_NAME = "construcciones"

def load_from_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM construcciones", conn)
        conn.close()
        return df
    except Exception as e:
        return pd.DataFrame()

# Configuración de la App Pública - LOOK PREMIUM
st.set_page_config(page_title="J&E Soluciones - Visor Inmobiliario", layout="wide", page_icon="🏢", initial_sidebar_state="collapsed")

# Estilos personalizados CSS Global Premium
st.markdown("""
<style>
    /* Fondo azul más oscuro y corporativo para Main y Sidebar */
    .stApp > header { background-color: transparent !important; }
    .stApp, .stAppViewContainer { background-color: #081a30 !important; }
    [data-testid="stSidebar"] { background-color: #051424 !important; }
    
    /* Textos en contenedores principales */
    h1, h2, h3, h4, h5, h6, .stMarkdown, label { color: white !important; }
    
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
    
    /* Pestañas */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; margin-bottom: 20px; }
    .stTabs [data-baseweb="tab"] { background-color: transparent !important; border: 1px solid rgba(255,255,255,0.2) !important; padding: 15px 25px; font-weight: 600; font-size: 16px; border-radius: 5px 5px 0 0; color: #cbd5e1 !important; }
    .stTabs [aria-selected="true"] { background-color: rgba(255,255,255,0.15) !important; border-bottom: 3px solid #60a5fa !important; color: white !important; }
    
    /* Cards HTML */
    .metric-card { background: rgba(255,255,255,0.1); border-left: 6px solid #60a5fa; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); transition: transform 0.2s; backdrop-filter: blur(5px); }
    .metric-card:hover { transform: translateY(-3px); }
    .metric-label { font-size: 14px; color: #bfdbfe; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; }
    .metric-value { font-size: 32px; color: white; font-weight: 900; margin-top: 8px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
</style>
""", unsafe_allow_html=True)

# --- SISTEMA DE CONTROL DE USUARIOS (LOGIN) ---
# Se importa el diccionario de contraseñas desde el archivo exterior
from seguridad import USUARIOS_AUTORIZADOS

def check_login():
    """Retorna True si el usuario ya está autenticado, de lo contrario muestra el formulario de Login"""
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        st.markdown("<h2 style='text-align: center; margin-top: 100px; color: white;'>🔒 Acceso Restringido - J&E Soluciones</h2>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #bfdbfe;'>Por favor, ingresa tus credenciales corporativas para acceder al tablero.</p>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1.2, 1])
        with col2:
            with st.form("login_form"):
                usuario = st.text_input("👤 Usuario", placeholder="Ej: gerencia")
                clave = st.text_input("🔑 Contraseña", type="password", placeholder="Tú contraseña")
                submit = st.form_submit_button("Ingresar al Sistema")
                
                if submit:
                    if usuario in USUARIOS_AUTORIZADOS and USUARIOS_AUTORIZADOS[usuario] == clave:
                        st.session_state["autenticado"] = True
                        st.session_state["usuario_actual"] = usuario
                        st.rerun()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos. Verifica e intenta de nuevo.")
        return False
    return True

# --- UI PRINCIPAL ---
if check_login():
    col_logo, col_title, col_logout = st.columns([1, 3.5, 0.5])
    with col_logo:
        try:
            logo_path = os.path.join(BASE_DIR, "logo.png")
            st.image(logo_path, use_container_width=True)
        except:
            st.write("🏢")
    with col_title:
        st.markdown("<h1 style='margin-bottom: 0px; padding-bottom: 0;'>J&E Soluciones</h1>", unsafe_allow_html=True)
        st.markdown("<h4 style='margin-top: 5px; color: #bfdbfe !important;'>Tablero Analítico de Licencias y Construcciones</h4>", unsafe_allow_html=True)
    with col_logout:
        # Botón sutil para cerrar sesión
        st.write("")
        st.write("")
        if st.button("🚪 Salir"):
            st.session_state["autenticado"] = False
            st.rerun()
            
    st.markdown("---")

    # --- CARGAR DATOS DESDE LA BASE DE DATOS MAESTRA ---
    df = load_from_db()

    if not df.empty:
        
        # 0. NORMALIZACIÓN SEMÁNTICA DE MUNICIPIOS
        df['municipio'] = df['municipio'].astype(str).str.upper()
        df['municipio'] = df['municipio'].replace(
            ['ITAGUI', 'ITAGUÍ', 'ITAGÜI', 'ITAGÚI', 'ITAGÚÍ', 'ITÁGUI'], 
            'ITAGÜÍ'
        )
        
        # 1. FORZAR ORDENAMIENTO POR ÁREA (Mayor a Menor) Y LIMPIAR ÍNDICES
        df['area_m2'] = pd.to_numeric(df['area_m2'], errors='coerce').fillna(0)
        df = df.sort_values(by="area_m2", ascending=False).reset_index(drop=True)
        
        # Layout Premium - Métricas como Cards Reales (usando HTML/CSS inline)
        html_metrics = f"""
        <div style="display: flex; gap: 20px; margin-bottom: 30px;">
            <div style="flex: 1;" class="metric-card">
                <div class="metric-label">Obras Detectadas</div>
                <div class="metric-value">{len(df)}</div>
            </div>
            <div style="flex: 1;" class="metric-card">
                <div class="metric-label">Total Área Proyectada (m²)</div>
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
        tab1, tab2, tab3 = st.tabs(["📋 Inteligencia de Base de Datos", "🗺️ Geo-Localizador Satelital", "📊 Analíticas Visuales"])
        
        with tab1:
            st.markdown("### 🗃️ Navegador Principal")
            st.markdown("<span style='color: #bfdbfe; font-size: 15px;'>Para acceder a los reportes originales, selecciona cualquier fila de la tabla a continuación.</span>", unsafe_allow_html=True)
            st.markdown("---")
            
            # Split layout para ver Tabla y PDF a la vez (Pantalla Dividida)
            view_col1, view_col2 = st.columns([1.5, 1], gap="large")
            
            with view_col1:
                # 2. LOGICA DE FILTRO POR FECHA ORDENADA CRONOLÓGICAMENTE
                fechas_reales = pd.to_datetime(df['fecha'], errors='coerce', dayfirst=True)
                df['periodo_dt'] = fechas_reales.dt.to_period('M')
                df['Mes_Periodo'] = df['periodo_dt'].dt.strftime('%m-%Y').fillna('Indeterminado')
                
                periodos_ordenados = sorted([p for p in df['periodo_dt'].unique() if not pd.isna(p)], reverse=True)
                opciones_periodo = ['Todos los periodos'] + [p.strftime('%m-%Y') for p in periodos_ordenados]
                if 'Indeterminado' in df['Mes_Periodo'].values:
                    opciones_periodo.append('Indeterminado')
                
                f_col1, f_col2 = st.columns(2)
                
                with f_col1:
                    filtro_mes = st.selectbox("📅 Filtrar Resoluciones por Mes:", opciones_periodo)
                
                with f_col2:
                    opciones_muni = ['Todos los municipios'] + sorted(list(df['municipio'].dropna().unique()))
                    filtro_muni = st.selectbox("📍 Filtrar por Municipio:", opciones_muni)
                
                # Encadenamiento de filtros interactivos
                df_mostrar = df.copy()
                if filtro_mes != 'Todos los periodos':
                    df_mostrar = df_mostrar[df_mostrar['Mes_Periodo'] == filtro_mes]
                
                if filtro_muni != 'Todos los municipios':
                    df_mostrar = df_mostrar[df_mostrar['municipio'] == filtro_muni]
                
                
                # Mostramos dataframe filtrado y sin columnas técnicas
                event = st.dataframe(
                    df_mostrar.drop(columns=['id', 'fecha_extraccion', 'Mes_Periodo', 'periodo_dt'], errors='ignore'), 
                    use_container_width=True,
                    on_select="rerun",
                    selection_mode="single-row",
                    hide_index=True
                )
                csv = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button("📥 Descargar Datos Crudos (CSV)", csv, "reporte_construcciones_publico.csv", "text/csv")
                
            with view_col2:
                st.markdown("#### 🔍 Soporte Legal")
                selected_pdf = None
                if getattr(event, "selection", None) is not None and len(event.selection.rows) > 0:
                    row_idx = event.selection.rows[0]
                    selected_pdf = df_mostrar.iloc[row_idx]['archivo']
                    
                if selected_pdf:
                    st.markdown(f"📄 **Archivo Vinculado:** `{selected_pdf}`")
                    pdf_path = None
                    # Buscamos en carpetas locales asumiendo la estructura actual.
                    # En un entorno de cloud deployment requeriría configuración de S3 o Google Cloud Storage.
                    search_dirs = [Path.cwd() / "Descargas" / "Itagui", Path.cwd() / "Descargas" / "Itagui_2", Path.cwd() / "Tipos Pdf"]
                    for d in search_dirs:
                        if (d / selected_pdf).exists():
                            pdf_path = d / selected_pdf
                            break
                            
                    if pdf_path:
                        with open(pdf_path, "rb") as f:
                            pdf_bytes_down = f.read()
                    else:
                        # Si no está local, buscar en la nube (Supabase)
                        with st.spinner("Descargando PDF desde la Nube..."):
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
                        st.download_button(label="📥 Descargar Documento (Local/Nube)", data=pdf_bytes_down, file_name=selected_pdf, mime="application/pdf")
                        
                        with st.container(height=600):
                            try:
                                # Renderizado desde bytes en memoria
                                doc = fitz.open(stream=pdf_bytes_down, filetype="pdf")
                                for page_num in range(len(doc)):
                                    page = doc.load_page(page_num)
                                    pix = page.get_pixmap(dpi=150)
                                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                                    st.image(img, use_container_width=True, caption=f"Página {page_num + 1} de {len(doc)}")
                                doc.close()
                            except Exception as e:
                                st.warning(f"La vista previa del PDF no se pudo cargar: {e}")
                    else:
                        st.error("❌ El archivo no está disponible ni en local ni en la nube.")
                else:
                    st.info("👈 Haz clic en cualquier resolución listada a la izquierda para intentar previsualizar su documento oficial en este espacio.")

        with tab2:
            st.markdown("### 🗺️ Radar Inteligente de Obras Georreferenciadas")
            if 'lat' in df.columns and 'lon' in df.columns:
                df_map = df.dropna(subset=['lat', 'lon'])
                # Filtramos latitud 0
                df_map = df_map[(df_map['lat'] != 0) & (df_map['lon'] != 0)]
                
                if not df_map.empty:
                    m = folium.Map(location=[df_map['lat'].mean(), df_map['lon'].mean()], zoom_start=14, tiles="CartoDB positron")
                    for idx, row in df_map.iterrows():
                        html_popup = f"""
                        <div style='font-family: Arial; font-size: 13px; min-width: 200px;'>
                            <div style='background-color:#1e4b7a; color:white; padding:5px; border-radius:3px; margin-bottom:5px; font-weight:bold;'>
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
                            tooltip=f"Ver detalles: {row['direccion']}",
                            icon=folium.Icon(color="darkblue", icon="info-sign")
                        ).add_to(m)
                    st_folium(m, width="100%", height=600, returned_objects=[])
                else:
                    st.info("No hay ubicaciones pre-calculadas en la base de datos principal todavía.")
            else:
                st.info("Las coordenadas no han sido calculadas por el sistema administrador.")

        with tab3:
            st.markdown("### 📊 Reportes Gerenciales y Dashboarding")
            c1, c2 = st.columns(2)
            with c1:
                fig = px.bar(
                    df, x="municipio", y="area_m2", color="municipio", 
                    title="Distribución de Metros Cuadrados", 
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
                        df, names="niveles", title="Composición por Cantidad de Niveles", 
                        hole=0.45, template="plotly_dark"
                    )
                    fig2.update_layout(
                        title_font_size=18, title_font_weight="bold", title_font_color="white",
                        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig2, use_container_width=True)

    else:
        st.info("ℹ️ El tablero se encuentra actualmente sin conexiones a bases de datos válidas o no posee registros públicos.")
