import streamlit as st
import requests
import pandas as pd
from streamlit_js_eval import get_geolocation
from datetime import datetime

# Configuramos la web para que parezca que sabemos lo que hacemos
st.set_page_config(page_title="ASIR GPS Control", page_icon="🕒")

API_URL = "http://backend:8000"

# Memoria de pez para que Streamlit no olvide quién eres al recargar
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = {}

# Si no has pasado por el login, no ves ni los buenos días
if not st.session_state.logged_in:
    st.title("🔐 Identifícate o vete a casa")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Clave", type="password")
        if st.form_submit_button("Entrar"):
            try:
                res = requests.post(f"{API_URL}/login?email={email}&password={password}")
                if res.status_code == 200:
                    st.session_state.logged_in = True
                    st.session_state.user_info = res.json()
                    st.rerun()
                else: st.error("Email o clave mal. Concéntrate.")
            except: st.error("Servidor KO. El Admin (tú) ha roto algo.")
    st.stop()

# Menú lateral para sentirte importante
user = st.session_state.user_info
st.sidebar.success(f"Usuario: {user['nombre']}")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.logged_in = False
    st.rerun()

menu = ["Fichar", "Mis Registros"]
if user['rol'] == 'admin': menu.append("Administración")
choice = st.sidebar.selectbox("¿A dónde vas?", menu)

if choice == "Fichar":
    st.title("🚀 Registro de Jornada")
    loc = get_geolocation() # Intentamos espiar tu posición
    
    opciones = {"0000 - ENTRADA": "entrada", "0001 - DESCANSO": "descanso", 
                "0005 - COMIDA": "comida", "0007 - SALIDA": "salida"}
    seleccion = st.selectbox("¿Qué acción vas a realizar?", list(opciones.keys()))

    if loc:
        c = loc.get('coords', loc)
        lat, lon = c.get('latitude', 36.68), c.get('longitude', -6.12)
        if st.button("Confirmar Fichaje"):
            requests.post(f"{API_URL}/fichar/{user['user_id']}?tipo={opciones[seleccion]}&lat={lat}&lon={lon}")
            st.success(f"Registrado: {seleccion}. No te acostumbres.")
    else: st.warning("Esperando GPS... o que dejes de bloquearlo.")

elif choice == "Mis Registros":
    st.title("📊 Tu historial (y tus horas extra)")
    res = requests.get(f"{API_URL}/fichajes/{user['user_id']}")
    if res.status_code == 200 and res.json():
        df = pd.DataFrame(res.json())
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # --- CÁLCULO DE HORAS (Matemáticas para adultos) ---
        hoy = datetime.now().date()
        df_hoy = df[df['timestamp'].dt.date == hoy].sort_values('timestamp')
        
        if len(df_hoy) >= 2:
            h_in = df_hoy[df_hoy['tipo'] == 'entrada']['timestamp'].min()
            h_out = df_hoy[df_hoy['tipo'] == 'salida']['timestamp'].max()
            if h_in and h_out:
                total = (h_out - h_in).total_seconds() / 3600
                neto = max(0, total 1)  # Restamos la hora de comer que te hemos regalado
                extra = max(0, neto - 8) # Más de 8h es explotación o vicio
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Horas Totales", f"{total:.2f}h")
                c2.metric("Trabajo Neto", f"{neto:.2f}h")
                c3.metric("Extras 🔥", f"{extra:.2f}h")

        st.dataframe(df[['tipo', 'timestamp', 'latitud', 'longitud']])
        
        # El mapa para ver si fichas desde el bar
        m_data = df[['latitud', 'longitud']].rename(columns={'latitud':'lat', 'longitud':'lon'}).dropna()
        st.map(m_data)

elif choice == "Administración":
    st.title("🛡️ Panel de Dios (Admin)")
    t1, t2 = st.tabs(["Lista Usuarios", "Alta Nueva"])
    with t1:
        r = requests.get(f"{API_URL}/usuarios/")
        st.dataframe(pd.DataFrame(r.json()))
    with t2:
        with st.form("alta"):
            n = st.text_input("Nombre"); e = st.text_input("Email"); p = st.text_input("Pass")
            r_rol = st.selectbox("Rol", ["user", "admin"])
            if st.form_submit_button("Crear"):
                requests.post(f"{API_URL}/usuarios/?nombre={n}&email={e}&password={p}&rol={r_rol}")
                st.success("Súbdito creado. A producir.")
