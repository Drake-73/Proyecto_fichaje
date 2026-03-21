import streamlit as st
import requests
import os
import pandas as pd
from streamlit_js_eval import get_geolocation
from datetime import datetime

# Configuración de la web
st.set_page_config(page_title="ASIR GPS Control - El Gran Hermano Laboral", 
                   page_icon="🕒",
                   layout="wide",
                   initial_sidebar_state="expanded")

# Direcciones (Interna para Streamlit, Pública para Firefox)
API_URL = os.getenv("API_URL", "http://backend:8000")
URL_PUBLICA = "http://localhost:8000" 

# Gestión de sesión
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_info = {}
if "seccion" not in st.session_state:
    st.session_state.seccion = "Fichar"

# --- BLOQUE DE SEGURIDAD ---
if not st.session_state.logged_in:
    st.title("🔐 Identifícate o vete a casa")
    with st.form("login_form"):
        email = st.text_input("Email corporativo")
        password = st.text_input("Clave", type="password")
        if st.form_submit_button("Entrar a producir"):
            try:
                res = requests.post(f"{API_URL}/login", json={"email": email, "password": password})
                if res.status_code == 200:
                    st.session_state.logged_in = True
                    st.session_state.user_info = res.json()
                    st.rerun()
                else:
                    st.error("Credenciales de chiste. Reinténtalo.")
            except:
                st.error("Servidor KO. Revisa tus contenedores Docker.")
    st.stop()

user = st.session_state.user_info
st.sidebar.success(f"Bienvenido, recurso humano: {user['nombre']}")
st.sidebar.title("🎮 Panel de Control")

# Navegación
if st.sidebar.button("🚀 Fichar ahora", use_container_width=True):
    st.session_state.seccion = "Fichar"
if st.sidebar.button("📊 Mis Registros", use_container_width=True):
    st.session_state.seccion = "Mis Registros"

if user['rol'] == 'admin':
    try:
        r_p_count = requests.get(f"{API_URL}/admin/preavisos/").json()
        pendientes_n = len([p for p in r_p_count if p.get('estado', 'pendiente') == 'pendiente'])
        label_admin = f"🛡️ Administración {'🔴' if pendientes_n > 0 else ''}"
    except:
        label_admin = "🛡️ Administración"
    if st.sidebar.button(label_admin, use_container_width=True):
        st.session_state.seccion = "Administración"

st.sidebar.divider()
if st.sidebar.button("🏃‍♂️ CERRAR SESIÓN", use_container_width=True):
    st.session_state.logged_in = False
    st.rerun()

choice = st.session_state.seccion

# --- SECCIÓN: FICHAR ---
if choice == "Fichar":
    st.title("🚀 Registro de Jornada - Te estamos viendo")
    
    st.subheader("📩 Tus Documentos (El Jefe quiere que leas)")
    try:
        res_docs = requests.get(f"{API_URL}/mis_documentos/{user['user_id']}")
        if res_docs.status_code == 200:
            docs_list = res_docs.json()
            if docs_list:
                for d in docs_list:
                    est = "✅ Leído" if d.get('leido') else "🆕 ¡PULSA AQUÍ!"
                    st.markdown(f"{est} - [{d.get('titulo')}]({URL_PUBLICA}/leer_documento/{d.get('id')})")
            else:
                st.info("Sin documentos nuevos.")
    except:
        st.error("Error al cargar documentos.")

    st.divider()
    loc = get_geolocation() 
    lat, lon = (loc.get('coords', loc).get('latitude'), loc.get('coords', loc).get('longitude')) if loc else (None, None)
    
    opts = {"0000 - ENTRADA": "entrada", "0001 - DESCANSO": "descanso", "0005 - COMIDA": "comida", "0007 - SALIDA": "salida"}
    sel = st.selectbox("Estado actual:", list(opts.keys()))

    if st.button("Confirmar Fichaje (y enviar posición)", use_container_width=True):
        f_lat, f_lon = (lat if lat else 36.68, lon if lon else -6.12)
        requests.post(f"{API_URL}/fichar/{user['user_id']}", json={"tipo": opts[sel], "lat": f_lat, "lon": f_lon})
        st.success("✅ Fichaje registrado.")

    st.divider()
    st.subheader("📝 ¿Vas a faltar? Miénteme aquí")
    with st.form("form_preaviso_tropa", clear_on_submit=True):
        t_p = st.selectbox("Incidencia:", ["Retraso", "Falta"])
        f_p = st.date_input("Día:")
        m_p = st.text_area("Motivo:")
        if st.form_submit_button("Enviar Aviso"):
            requests.post(f"{API_URL}/preavisos/", json={"usuario_id": user['user_id'], "tipo": t_p, "fecha": str(f_p), "motivo": m_p})
            st.success("Aviso enviado.")

    st.subheader("📋 Estado de mis avisos")
    try:
        res_m = requests.get(f"{API_URL}/admin/preavisos/")
        if res_m.status_code == 200:
            mis = [p for p in res_m.json() if p.get('usuario_nombre') == user['nombre']]
            if mis:
                for mp in mis:
                    est_mp = mp.get('estado', 'pendiente')
                    c = "🟢" if est_mp == 'aceptado' else "🔴" if est_mp == 'rechazado' else "🟡"
                    st.write(f"{c} {mp.get('fecha')} - {mp.get('tipo')}: {est_mp.upper()}")
            else:
                st.info("No tienes avisos registrados.")
    except:
        st.write("Cargando estados...")

# --- SECCIÓN: MIS REGISTROS ---
elif choice == "Mis Registros":
    st.title("📊 Tu historial")
    res = requests.get(f"{API_URL}/fichajes/{user['user_id']}")
    if res.status_code == 200 and res.json():
        df = pd.DataFrame(res.json())
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        hoy = datetime.now().date()
        df_h = df[df['timestamp'].dt.date == hoy].sort_values('timestamp')
        if len(df_h) >= 2:
            h_trab = 0
            ini = None
            for _, fila in df_h.iterrows():
                if fila['tipo'] == 'entrada': ini = fila['timestamp']
                elif fila['tipo'] in ['comida', 'salida', 'descanso'] and ini:
                    h_trab += (fila['timestamp'] - ini).total_seconds() / 3600
                    ini = None
            if h_trab > 0:
                c1, c2, c3 = st.columns(3)
                c1.metric("Horas Netas", f"{h_trab:.2f}h")
                c2.metric("Objetivo", "8.00h")
                c3.metric("Extras 🔥", f"{max(0, h_trab - 8):.2f}h")

        st.download_button("📥 Descargar CSV", data=df.to_csv(index=False).encode('utf-8'), file_name="mis_fichajes.csv", mime="text/csv")
        st.dataframe(df.assign(timestamp=df['timestamp'].dt.strftime('%d/%m/%Y %H:%M:%S'))[['tipo', 'timestamp', 'latitud', 'longitud']], use_container_width=True)

        st.subheader("📍 Mapa de tus movimientos")
        m_data = df[['latitud', 'longitud']].rename(columns={'latitud':'lat', 'longitud':'lon'}).dropna()
        if not m_data.empty: st.map(m_data, zoom=13)

# --- SECCIÓN: ADMINISTRACIÓN ---
elif choice == "Administración":
    # Creamos las 4 pestañas de nuevo
    t1, t2, t3, t4 = st.tabs(["🕵️ Monitor de Tropa", "🆕 Alta de Esclavos", "⚠️ Alertas", "📂 Gestión Doc/Preavisos"])
    
    with t1:
        st.header("🕵️ Monitor en Tiempo Real")
        r_mon = requests.get(f"{API_URL}/estado_usuarios/")
        if r_mon.status_code == 200:
            for emp in r_mon.json():
                c_n, c_e, c_h = st.columns([2, 1, 1])
                c_n.write(f"**{emp.get('nombre')}** ({emp.get('email')})")
                status = emp.get('ultimo_evento')
                if status == "entrada": c_e.success("🟢 Trabajando")
                elif status in ["comida", "descanso"]: c_e.warning("🟡 Esquequeado")
                elif status == "salida": c_e.error("🔴 Fuera")
                else: c_e.info("⚪ Sin noticias")
                c_h.write(f"🕒 {emp.get('hora', '--:--')}")
                st.divider()
        else:
            st.error("No se puede espiar a la tropa ahora mismo.")

    with t2:
        st.header("🆕 Registro de Súbditos")
        with st.form("nuevo_u_form", clear_on_submit=True):
            n = st.text_input("Nombre completo")
            e = st.text_input("Email corporativo")
            p = st.text_input("Contraseña provisional", type="password")
            r_rol = st.selectbox("Rol en la empresa", ["user", "admin"])
            if st.form_submit_button("Dar de alta"):
                res_new = requests.post(f"{API_URL}/usuarios/", json={"nombre": n, "email": e, "password": p, "rol": r_rol})
                if res_new.status_code == 200:
                    st.success(f"Usuario {n} creado. Que empiece a producir.")
                else:
                    st.error("Error al crear el usuario. ¿Ya existe ese email?")

    with t3:
        st.header("⚠️ Historial de Incidencias")
        if st.button("🔄 Actualizar Alertas del Día"):
            requests.get(f"{API_URL}/alertas_fichaje/")
            st.toast("Alertas refrescadas")
            
        res_users_alert = requests.get(f"{API_URL}/usuarios/")
        if res_users_alert.status_code == 200:
            u_list = {f"{u['nombre']}": u['id'] for u in res_users_alert.json()}
            sospechoso = st.selectbox("Seleccionar sospechoso:", list(u_list.keys()))
            if st.button(f"Ver historial de {sospechoso}"):
                uid = u_list[sospechoso]
                r_hist = requests.get(f"{API_URL}/historial_alertas/{uid}")
                if r_hist.status_code == 200 and r_hist.json():
                    st.table(pd.DataFrame(r_hist.json())[['fecha', 'motivo']])
                else:
                    st.success("Expediente limpio... de momento.")

    with t4:
        st.header("📂 Gestión de Documentos y Sentencias")
        
        # 1. Envío de archivos
        res_u_doc = requests.get(f"{API_URL}/usuarios/")
        u_dict_doc = {u['nombre']: u['id'] for u in res_u_doc.json()} if res_u_doc.status_code == 200 else {}
        
        with st.expander("📤 Enviar nuevo archivo físico"):
            with st.form("env_arch_form", clear_on_submit=True):
                v_dest = st.selectbox("Destinatario:", list(u_dict_doc.keys()))
                v_tit = st.text_input("Título del documento:")
                v_file = st.file_uploader("Archivo:", type=['pdf', 'docx', 'jpg', 'png'])
                if st.form_submit_button("Lanzar"):
                    if v_file and v_tit:
                        requests.post(f"{API_URL}/subir_documento/", data={"usuario_id": u_dict_doc[v_dest], "titulo": v_tit}, files={"archivo": (v_file.name, v_file.getvalue())})
                        st.success("Enviado.")

        # 2. Control de lectura
        st.subheader("📊 Chivatazo de Lectura")
        r_ctrl = requests.get(f"{API_URL}/admin/documentos/")
        if r_ctrl.status_code == 200 and r_ctrl.json():
            st.table([{"Empleado": d.get("usuario_nombre"), "Doc": d.get("titulo"), "Leído": "✅" if d.get("leido") else "❌"} for d in r_ctrl.json()])

        # 3. Juez de Preavisos (EL MAZO)
        st.divider()
        st.subheader("📬 Juez de Preavisos")
        res_p_adm = requests.get(f"{API_URL}/admin/preavisos/")
        if res_p_adm.status_code == 200:
            p_p = [p for p in res_p_adm.json() if p.get('estado', 'pendiente') == 'pendiente']
            if p_p:
                for p in p_p:
                    with st.container(border=True):
                        c_inf, c_btns = st.columns([3, 2])
                        c_inf.write(f"**{p.get('usuario_nombre')}** - {p.get('tipo')} ({p.get('fecha')})\n\n{p.get('motivo')}")
                        b_ok, b_no = c_btns.columns(2)
                        if b_ok.button("✅ Aceptar", key=f"ok_adm_{p['id']}", use_container_width=True):
                            requests.post(f"{API_URL}/admin/decidir_preaviso/{p['id']}", json={"estado": "aceptado"})
                            st.rerun()
                        if b_no.button("❌ Rechazar", key=f"no_adm_{p['id']}", use_container_width=True, type="primary"):
                            requests.post(f"{API_URL}/admin/decidir_preaviso/{p['id']}", json={"estado": "rechazado"})
                            st.rerun()
            else: st.info("Sin juicios pendientes.")