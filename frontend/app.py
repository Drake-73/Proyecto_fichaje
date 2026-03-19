import streamlit as st
import requests
import pandas as pd
from streamlit_js_eval import get_geolocation

st.set_page_config(page_title="Acceso ASIR GPS", page_icon="🔐")

API_URL = "http://backend:8000"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = {}

if not st.session_state.logged_in:
    st.title("🔐 Control de Acceso")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Entrar")
        if submit:
            try:
                res = requests.post(f"{API_URL}/login?email={email}&password={password}")
                if res.status_code == 200:
                    st.session_state.logged_in = True
                    st.session_state.user_info = res.json()
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
            except:
                st.error("Error de conexión con el servidor")
    st.stop()

user = st.session_state.user_info
st.sidebar.success(f"Usuario: {user['nombre']}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logged_in = False
    st.rerun()

menu = ["Fichar", "Ver mis registros"]
if user['rol'] == 'admin':
    menu.append("Administración")

choice = st.sidebar.selectbox("Menú", menu)

if choice == "Fichar":
    st.title(f"🚀 Panel de Fichaje")
    loc = get_geolocation()
    
    opciones_fichaje = {
        " ENTRADA TRABAJO": "entrada",
        " DESCANSO": "descanso",
        " COMIDA": "comida",
        " AUSENCIA PTE. JUSTIFICAR": "ausencia",
        " SALIDA TRABAJO": "salida",
        " HUELGA": "huelga"
    }

    seleccion = st.selectbox("¿Qué acción vas a realizar?", list(opciones_fichaje.keys()))
    tipo_cod = opciones_fichaje[seleccion]

    if loc:
        coords = loc.get('coords', loc)
        lat = coords.get('latitude') or 36.6850
        lon = coords.get('longitude') or -6.1260
        
        st.info(f"📍 Ubicación detectada")
        
        if st.button("Confirmar Registro"):
            try:
                res = requests.post(f"{API_URL}/fichar/{user['user_id']}?tipo={tipo_cod}&lat={lat}&lon={lon}")
                if res.status_code == 200:
                    st.success(f"Registrado: {seleccion}")
                else:
                    st.error("Error en el servidor")
            except:
                st.error("Error de conexión")
    else:
        st.warning("Esperando GPS...")

elif choice == "Ver mis registros":
    st.subheader("📍 Tu Actividad")
    res = requests.get(f"{API_URL}/fichajes/{user['user_id']}")
    if res.status_code == 200:
        datos = res.json()
        if datos:
            df = pd.DataFrame(datos)
            
            st.write("📂 **Exportar:**")
            st.download_button("Descargar CSV", df.to_csv(index=False), f"fichajes_{user['user_id']}.csv", "text/csv")
            
            st.dataframe(df[['tipo', 'timestamp', 'latitud', 'longitud']])
            
            map_data = df[['latitud', 'longitud']].dropna()
            map_data['lat'] = pd.to_numeric(map_data['latitud'], errors='coerce')
            map_data['lon'] = pd.to_numeric(map_data['longitud'], errors='coerce')
            map_data = map_data.dropna(subset=['lat', 'lon'])
            
            if not map_data.empty:
                st.map(map_data)

elif choice == "Administración":
    st.title("🛡️ Panel de Control (Admin)")
    
    tab1, tab2 = st.tabs(["👥 Gestión de Usuarios", "📊 Fichajes Globales"])
    
    with tab1:
        st.subheader("Usuarios Registrados")
        try:
            res = requests.get(f"{API_URL}/usuarios/")
            if res.status_code == 200:
                usuarios = res.json()
                st.dataframe(pd.DataFrame(usuarios))
            else:
                st.error("No se pudo obtener la lista de usuarios")
        except:
            st.error("Error de conexión con el Backend")

    with tab2:
        st.subheader("Historial de toda la empresa")
        # Necesitamos un endpoint para ver TODO. Por ahora usaremos el de listar usuarios
        # pero lo ideal es ver los fichajes. Vamos a mostrar un mensaje de aviso:
        st.info("Aquí verás los fichajes de todos los empleados en el futuro.")
        if st.button("Actualizar Vista Global"):
            st.rerun()
