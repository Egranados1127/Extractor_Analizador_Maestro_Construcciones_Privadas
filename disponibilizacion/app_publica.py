import streamlit as st
import traceback

try:
    import pandas as pd
    import os
    import sqlite3
    import time
    import plotly.express as px
    from pathlib import Path
    from geopy.geocoders import Nominatim, ArcGIS
    import folium
    from streamlit_folium import st_folium
    import requests
    import unicodedata
    import unicodedata
except Exception as builtin_or_import_error:
    st.error(f"🚨 STREAMLIT FATAL IMPORT ERROR: {builtin_or_import_error}")
    st.code(traceback.format_exc())
    st.stop()

# Configuración de la Base de Datos Local y Nube
DB_PATH = "master_construcciones.db"
SUPABASE_URL = "https://oubqiodpjhkdrpeukvag.supabase.co"
SUPABASE_KEY = "sb_secret_GUCb7gIZQguts5VjPsxeww_73QJsQo4"
BUCKET_NAME = "construcciones"

@st.cache_data(ttl=300)
def load_from_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT * FROM construcciones", conn)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_public_from_db():
    try:
        conn = sqlite3.connect('master_construcciones.db')
        df_pub = pd.read_sql_query("SELECT * FROM obras_publicas WHERE tag_fiel = 'APLICA' ORDER BY fecha_publicacion DESC", conn)
        conn.close()
        return df_pub
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_firmas_from_db():
    try:
        conn = sqlite3.connect('master_construcciones.db')
        df_firmas = pd.read_sql_query("SELECT * FROM firmas_electricas ORDER BY id DESC", conn)
        conn.close()
        return df_firmas
    except Exception:
        return pd.DataFrame()

st.set_page_config(page_title="Radar Maestro - FIEL Ferreteros", layout="wide", page_icon="🏗️")

st.markdown("""
<style>
    .stApp > header { background-color: transparent !important; }
    .stApp, .stAppViewContainer { background-color: #081a30 !important; }
    [data-testid="stSidebar"] { background-color: #051424 !important; }
    h1, h2, h3, h4, h5, h6, .stMarkdown, label { color: white !important; }
    
    [data-baseweb="select"] > div { background-color: #102a43 !important; border: 1px solid #1e4b7a !important; color: white !important; }
    [data-baseweb="select"] * { color: white !important; }
    [data-baseweb="popover"] > div, ul[data-baseweb="menu"] { background-color: #102a43 !important; }
    ul[data-baseweb="menu"] li { color: white !important; border-bottom: 1px solid rgba(255,255,255,0.05); }
    ul[data-baseweb="menu"] li:hover { background-color: #1e4b7a !important; }
    
    .stButton>button { border-radius: 10px; background: rgba(255,255,255,0.1) !important; color: white !important; border: 1px solid rgba(255,255,255,0.3) !important; font-weight: bold; backdrop-filter: blur(4px); transition: all 0.2s; }
    .stButton>button:hover { background: rgba(255,255,255,0.2) !important; border-color: white !important; }
    
    .stMetric { background-color: rgba(255,255,255,0.05); padding: 15px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.1); }
    .stMetric * { color: white !important; }
    [data-testid="stMetricValue"] { color: white !important; }
</style>
""", unsafe_allow_html=True)

col_logo, col_title = st.columns([1, 4])
with col_logo:
    try:
        st.image("logo.png", use_container_width=True)
    except:
        pass
with col_title:
    st.markdown("<h1 style='margin-bottom: 0px; padding-bottom: 0;'>FIEL Ferreteros</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='margin-top: 5px; color: #bfdbfe !important;'>Radar de Construcciones, Obras Públicas y Firmas (B2B)</h4>", unsafe_allow_html=True)
st.markdown("---")

df = load_from_db()
tab_privadas, tab_publicas, tab_firmas = st.tabs(["🏗️ Obras Privadas", "🏛️ Obras Públicas", "⚡ Firmas Eléctricas"])

# --- TAB 1: OBRAS PRIVADAS ---
with tab_privadas:
    if not df.empty:
        df['municipio'] = df['municipio'].str.upper()
        df['municipio'] = df['municipio'].replace(['ITAGUI', 'ITAGUÍ', 'ITAGÜI', 'ITAGÚI', 'ITAGÚÍ', 'ITÁGUI'], 'ITAGÜÍ')
        df['area_m2'] = pd.to_numeric(df['area_m2'], errors='coerce').fillna(0)
        df = df.sort_values(by="area_m2", ascending=False).reset_index(drop=True)

        st.markdown("""
        <style>
            .metric-card { background: rgba(255,255,255,0.1); border-left: 6px solid #60a5fa; padding: 25px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); transition: transform 0.2s; backdrop-filter: blur(5px); }
            .metric-card:hover { transform: translateY(-3px); }
            .metric-label { font-size: 14px; color: #bfdbfe; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; }
            .metric-value { font-size: 32px; color: white; font-weight: 900; margin-top: 8px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        </style>
        """, unsafe_allow_html=True)
        
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
        
        tab1, tab2, tab3 = st.tabs(["📋 Base de Datos y Documentos", "🗺️ Mapa Satelital Espacial", "📊 Analíticas Visuales"])

        with tab1:
            st.markdown("### 🗃️ Navegador Principal")
            st.markdown("<span style='color: #666; font-size: 15px;'>Para auditar la información, simplemente **haz clic en una fila** de la tabla de la izquierda y el documento soporte oficial se desplegará instantáneamente en el panel derecho.</span>", unsafe_allow_html=True)
            st.markdown("---")

            # Split layout para ver Tabla y PDF a la vez (Pantalla Dividida)
            view_col1, view_col2 = st.columns([1.5, 1], gap="large")

            with view_col1:
                fechas_reales = pd.to_datetime(df['fecha'], errors='coerce', dayfirst=True)
                df['periodo_dt'] = fechas_reales.dt.to_period('M')
                df['Mes_Periodo'] = df['periodo_dt'].dt.strftime('%m-%Y').fillna('Indeterminado')
                
                periodos_ordenados = sorted([p for p in df['periodo_dt'].unique() if not pd.isna(p)], reverse=True)
                opciones_periodo = ['Todos los periodos'] + [p.strftime('%m-%Y') for p in periodos_ordenados]
                if 'Indeterminado' in df['Mes_Periodo'].values: opciones_periodo.append('Indeterminado')

                f_col1, f_col2 = st.columns(2)
                with f_col1: filtro_mes = st.selectbox("📅 Filtro Cronológico (Mes):", opciones_periodo)
                with f_col2: 
                    opciones_muni = ['Todos los municipios'] + sorted(list(df['municipio'].dropna().unique()))
                    filtro_muni = st.selectbox("📍 Filtrar por Municipio:", opciones_muni)

                df_mostrar = df.copy()
                if filtro_mes != 'Todos los periodos': df_mostrar = df_mostrar[df_mostrar['Mes_Periodo'] == filtro_mes]
                if filtro_muni != 'Todos los municipios': df_mostrar = df_mostrar[df_mostrar['municipio'] == filtro_muni]

                try:
                    event = st.dataframe(
                        df_mostrar.drop(columns=['id', 'fecha_extraccion', 'Mes_Periodo', 'periodo_dt', 'lat', 'lon'], errors='ignore'), 
                        use_container_width=True,
                        on_select="rerun",
                        selection_mode="single-row",
                        hide_index=True
                    )
                except TypeError:
                    # Versión de Streamlit antigua en la nube (Falla silenciosa para evitar crash)
                    event = st.dataframe(
                        df_mostrar.drop(columns=['id', 'fecha_extraccion', 'Mes_Periodo', 'periodo_dt', 'lat', 'lon'], errors='ignore'), 
                        use_container_width=True,
                        hide_index=True
                    )
            
            with view_col2:
                st.markdown("#### 🔍 Visor de Soporte Legal")
                selected_pdf = None
                if getattr(event, "selection", None) is not None and len(event.selection.rows) > 0:
                    row_idx = event.selection.rows[0]
                    selected_pdf = df_mostrar.iloc[row_idx]['archivo']

                if selected_pdf:
                    st.markdown(f"📄 **Soporte Legal Activo:** `{selected_pdf}`")
                    pdf_bytes_down = None
                    
                    with st.spinner("Conectando con Supabase Cloud Storage para descargar..."):
                        clean_name = unicodedata.normalize('NFKD', selected_pdf).encode('ASCII', 'ignore').decode('utf-8')
                        url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{clean_name}"
                        try:
                            import requests
                            res = requests.get(url)
                            if res.status_code != 200:
                                url_auth = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{clean_name}"
                                headers = {"Authorization": f"Bearer {SUPABASE_KEY}", "apikey": SUPABASE_KEY}
                                res = requests.get(url_auth, headers=headers)

                            if res.status_code == 200:
                                pdf_bytes_down = res.content
                        except Exception as e:
                            st.error(f"Error de red: {e}")

                    if pdf_bytes_down:
                        st.download_button(label="📥 Descargar PDF Analizado (Nube)", data=pdf_bytes_down, file_name=selected_pdf, mime="application/pdf")

                        with st.container(height=600):
                            try:
                                import fitz
                                from PIL import Image
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
                        st.error("❌ El archivo no pudo ser ubicado en Supabase Cloud. Asegúrate de haber ejecutado sincronizar_nube.py")
                else:
                    st.info("👈 Selecciona cualquier fila en la tabla de la izquierda para abrir el documento instantáneamente aquí.")

        with tab2:
            st.markdown("### 🗺️ Visualización Estratégica Espacial")
            if 'lat' in df.columns and 'lon' in df.columns:
                df_map = df.dropna(subset=['lat', 'lon'])
                df_map = df_map[(df_map['lat'] != 0) & (df_map['lon'] != 0)]
                if not df_map.empty:
                    m = folium.Map(location=[df_map['lat'].mean(), df_map['lon'].mean()], zoom_start=11, tiles="CartoDB positron")
                    for idx, row in df_map.iterrows():
                        folium.Marker([row['lat'], row['lon']], popup=f"Uso: {row.get('tipo', 'O')}<br>Área: {row.get('area_m2', '?')} m2").add_to(m)
                    st_folium(m, width="100%", height=500, returned_objects=[])
        with tab3:
            c1, c2 = st.columns(2)
            with c1:
                fig = px.bar(df, x="municipio", y="area_m2", color="municipio", title="Área M2 por Municipio", template="plotly_dark")
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                if 'niveles' in df.columns and not df['niveles'].dropna().empty:
                    fig2 = px.pie(df, names="niveles", title="Distribución por Pisos", template="plotly_dark", hole=0.45)
                    st.plotly_chart(fig2, use_container_width=True)

# --- TAB 2: OBRAS PÚBLICAS ---
with tab_publicas:
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        st.title("🏛️ Radar de Licitaciones (SECOP)")
    with col_t2:
        if st.button("🔄 Actualizar SECOP (Nuevos)", use_container_width=True):
            with st.spinner("Buscando y filtrando con IA..."):
                try:
                    import scraper_secop
                    n = scraper_secop.update_obras_publicas()
                    st.success(f"Se añadieron {n} procesos al radar.")
                    time.sleep(2)
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    df_pub = load_public_from_db()
    if not df_pub.empty:
        df_pub['valor_estimado'] = pd.to_numeric(df_pub['valor_estimado'], errors='coerce').fillna(0)
        c1, c2 = st.columns(2)
        estados_disp = sorted(df_pub['estado'].dropna().unique().tolist())
        estado_filtro = c1.multiselect("Filtrar por Etapa:", estados_disp, default=[])
        muni_disp = sorted(df_pub['municipio'].dropna().unique().tolist())
        muni_filtro = c2.multiselect("Filtrar por Municipio:", muni_disp, default=[])
        
        df_pub_view = df_pub.copy().sort_values(by="valor_estimado", ascending=False).reset_index(drop=True)
        if estado_filtro: df_pub_view = df_pub_view[df_pub_view['estado'].isin(estado_filtro)]
        if muni_filtro: df_pub_view = df_pub_view[df_pub_view['municipio'].isin(muni_filtro)]
            
        m1, m2 = st.columns(2)
        m1.metric("Procesos en Pantalla", len(df_pub_view))
        m2.metric("Presupuesto", f"${df_pub_view['valor_estimado'].sum():,.0f} COP")
        
        df_show = df_pub_view.head(150)[['fecha_publicacion', 'municipio', 'entidad', 'estado', 'valor_estimado', 'url_proceso', 'descripcion']].copy()
        df_show['url_proceso'] = df_show['url_proceso'].apply(lambda x: f'<a href="{x}" target="_blank" style="color:#bfdbfe;">🔗 Enlace</a>')
        df_show['valor_estimado'] = df_show['valor_estimado'].apply(lambda x: f"$ {x:,.0f}")
        
        html_pub = f"""
        <style>.pub-table table {{ width: 100%; border-collapse: collapse; font-size: 13px; }} .pub-table th {{ background: rgba(255,255,255,0.1); color: white; padding: 8px; border-bottom: 2px solid white; text-align: left; }} .pub-table td {{ padding: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); color: #eeeeee; word-wrap: break-word; white-space: normal; }} .pub-table tr:hover {{ background: rgba(255,255,255,0.05); }}</style>
        <div class="pub-table" style="width: 100%;">{df_show.to_html(escape=False, index=False)}</div>
        """
        st.markdown(html_pub, unsafe_allow_html=True)

# --- TAB 3: FIRMAS B2B ---
with tab_firmas:
    st.title("⚡Radar de Firmas Eléctricas B2B")
    df_firmas = load_firmas_from_db()
    if not df_firmas.empty:
        scores_disp = sorted(df_firmas['score'].dropna().unique().tolist())
        score_filtro = st.multiselect("Filtrar por Relevancia (Score):", scores_disp, default=[])
        df_firmas_view = df_firmas.copy()
        if score_filtro: df_firmas_view = df_firmas_view[df_firmas_view['score'].isin(score_filtro)]
        df_firmas_view['url'] = df_firmas_view['url'].apply(lambda x: f'<a href="{x}" target="_blank" style="color:#bfdbfe;">🔗 Web</a>' if x else "-")
        df_firmas_view = df_firmas_view[['score', 'nombre', 'especialidad', 'contacto', 'resumen', 'url']]
        html_f = f"""
        <style>.f-table table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; }} .f-table th {{ background: rgba(255,255,255,0.1); color: white; padding: 10px; border-bottom: 2px solid #60a5fa; text-align: left; }} .f-table td {{ padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.05); color: #e2e8f0; word-wrap: break-word; white-space: normal; }} .f-table tr:hover {{ background: rgba(255,255,255,0.1); }}</style>
        <div class="f-table" style="width: 100%;">{df_firmas_view.to_html(escape=False, index=False)}</div>
        """
        st.markdown(html_f, unsafe_allow_html=True)
    else:
        st.info("💡 Aún no se han capturado firmas.")
