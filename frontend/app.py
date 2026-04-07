# Importamos todas las herramientas del taller. Probablemente usemos la mitad, pero es mejor que sobren.
import streamlit as st
import requests
import os
import pandas as pd
from streamlit_js_eval import get_geolocation
from datetime import datetime
# Configuramos la página. Título, icono... lo típico para que parezca profesional.
st.set_page_config(page_title="ASIR GPS Control", page_icon="🕒", layout="wide")

# ¿Dónde está el backend? Buena pregunta. Si no nos lo dicen, asumimos que está en un lugar mágico.
API_URL = os.getenv("API_URL", "http://backend:8000")
# Y la URL para que el usuario haga clic, porque claro, el navegador no sabe qué es 'backend:8000'.
URL_PUBLICA = "http://localhost:8000" 

# El estado de la sesión, nuestro castillo de naipes digital.
if "logged_in" not in st.session_state:
    # Empezamos asumiendo que nadie ha entrado. Seguridad ante todo.
    st.session_state.logged_in = False
    st.session_state.user_info = {}
if "seccion" not in st.session_state:
    # Por defecto, todo el mundo quiere fichar. O eso nos gusta pensar.
    st.session_state.seccion = "Fichar"

# El gran muro: si no estás en la lista, no pasas.
if not st.session_state.logged_in:
    st.title("🔐 Identifícate")
    with st.form("login"): # Un formulario para que nos den sus credenciales. Confiamos en que sean las suyas.
        e = st.text_input("Email")
        p = st.text_input("Clave", type="password")
        if st.form_submit_button("Entrar"):
            res = requests.post(f"{API_URL}/login", json={"email": e, "password": p})
            if res.status_code == 200:
                st.session_state.logged_in = True
                st.session_state.user_info = res.json(); st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# Si has llegado hasta aquí, enhorabuena. Te guardamos los datos para no volver a preguntar.
user = st.session_state.user_info
st.sidebar.success(f"Usuario: {user['nombre']}")

# La barra lateral, el menú de opciones para que el usuario se sienta con el control.
if st.sidebar.button("🚀 Fichar", use_container_width=True): st.session_state.seccion = "Fichar"
if st.sidebar.button("📊 Registros", use_container_width=True): st.session_state.seccion = "Registros"
if user['rol'] == 'admin':
    # Un botón secreto solo para los elegidos. El poder corrompe.
    if st.sidebar.button("🛡️ Administración", use_container_width=True): st.session_state.seccion = "Administración"

# La puerta de salida. No la usarán, ¿verdad?
if st.sidebar.button("🏃‍♂️ Salir", use_container_width=True):
    st.session_state.logged_in = False; st.rerun()

choice = st.session_state.seccion

# Sección de Fichaje: el corazón de esta humilde aplicación.
if choice == "Fichar":
    st.title("🚀 Fichar")
    # Primero, recordémosle al usuario los documentos que no ha leído. Presión social.
    res_d = requests.get(f"{API_URL}/mis_documentos/{user['user_id']}")
    if res_d.status_code == 200 and res_d.json():
        for d in res_d.json():
            st.markdown(f"{'✅' if d['leido'] else '🆕'} [{d['titulo']}]({URL_PUBLICA}/leer_documento/{d['id']})")
    
    # A ver, ¿dónde estás? Le preguntamos al navegador con la esperanza de que nos diga la verdad.
    loc = get_geolocation()
    if loc and 'coords' in loc:
        lat = loc['coords'].get('latitude', 36.68)
        lon = loc['coords'].get('longitude', -6.12)
    else:
        # Si falla, diremos que está en Jerez. Un lugar tan bueno como cualquier otro.
        lat, lon = 36.68, -6.12

    opts = {"ENTRADA": "entrada", "DESCANSO": "descanso", "COMIDA": "comida", "SALIDA": "salida"}
    sel = st.selectbox("Estado:", list(opts.keys()))
    if st.button("Confirmar", use_container_width=True):
        # El usuario presiona un botón para jurar que está trabajando. Nosotros solo registramos el evento.
        res_fichar = requests.post(f"{API_URL}/fichar/{user['user_id']}", json={"tipo": opts[sel], "lat": lat, "lon": lon})
        if res_fichar.status_code == 200:
            st.success(f"Fichaje registrado en ({lat}, {lon})")
        else:
            st.error("No se pudo registrar el fichaje.")

    st.subheader("📝 Preaviso")
    # Un pequeño formulario para que supliquen clemencia por sus futuras ausencias.
    with st.form("prev", clear_on_submit=True):
        tp = st.selectbox("Tipo", ["Retraso", "Falta"])
        fp = st.date_input("Día")
        mp = st.text_area("Motivo")
        if st.form_submit_button("Enviar"):
            res_prev = requests.post(f"{API_URL}/preavisos/", json={"usuario_id": user['user_id'], "tipo": tp, "fecha": str(fp), "motivo": mp})
            if res_prev.status_code == 200:
                st.success("Preaviso enviado correctamente.")
            else:
                st.error("No se pudo enviar el preaviso.")

# Sección de Registros: el pasado siempre vuelve.
elif choice == "Registros":
    st.title("📊 Historial")
    r = requests.get(f"{API_URL}/fichajes/{user['user_id']}")
    if r.status_code == 200 and r.json():
        # Convertimos su historial en un bonito DataFrame. Los datos son poder.
        df = pd.DataFrame(r.json())
        # Y por si quieren una copia para sus propios archivos... o para el abogado.
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Descargar historial en CSV", data=csv, file_name="historial_fichajes.csv", mime="text/csv")
        st.dataframe(df[['tipo', 'timestamp']], use_container_width=True)
        # Un mapa para que vean todos los sitios donde han estado... trabajando, claro.
        m_data = df[['latitud', 'longitud']].rename(columns={'latitud':'lat', 'longitud':'lon'}).dropna()
        if not m_data.empty: st.map(m_data)

# La joya de la corona: el panel del Gran Hermano.
elif choice == "Administración":
    st.title("🛡️ Panel de Control Superior (El Gran Hermano)")
    t1, t2, t3, t4 = st.tabs(["🕵️ Monitor", "🆕 Alta", "⚠️ Alertas", "📂 Gestión Doc/Preavisos"])
    
    with t1:
        # Aquí es donde el admin espía a sus súbditos en "tiempo real".
        st.header("🕵️ Monitor de Tropa en Tiempo Real")
        try:
            r_mon = requests.get(f"{API_URL}/estado_usuarios/")
            if r_mon.status_code == 200:
                for emp in r_mon.json():
                    with st.container(border=True):
                        c_n, c_e, c_h = st.columns([2, 1, 1])
                        c_n.write(f"**{emp.get('nombre')}** ({emp.get('email')})")
                        # Clasificamos su estado con un sistema de colores muy científico.
                        status = emp.get('ultimo_evento')
                        if status == "entrada": c_e.success("🟢 Trabajando")
                        elif status in ["comida", "descanso"]: c_e.warning("🟡 Esquequeado")
                        elif status == "salida": c_e.error("🔴 Fuera")
                        else: c_e.info("⚪ Sin noticias")
                        c_h.write(f"🕒 {emp.get('hora', '--:--')}")
        except:
            st.error("Error de conexión con el monitor.")

    with t2:
        # El mercado de nuevos fichajes.
        st.header("🆕 Registro de Nuevos Súbditos")
        with st.form("nuevo_u_form", clear_on_submit=True):
            n = st.text_input("Nombre completo")
            e = st.text_input("Email corporativo")
            p = st.text_input("Contraseña provisional", type="password")
            r_rol = st.selectbox("Rol en la empresa", ["user", "admin"])
            if st.form_submit_button("Dar de alta"):
                if n and e and p:
                    # Enviamos los datos al matadero digital.
                    res_new = requests.post(f"{API_URL}/usuarios/", json={"nombre": n, "email": e, "password": p, "rol": r_rol})
                    if res_new.status_code == 200:
                        st.success(f"Usuario {n} creado.")
                    else:
                        st.error("Error al crear.")

    with t3:
        # El muro de la vergüenza.
        st.header("⚠️ Historial de Incidencias")
        if st.button("🔄 Actualizar Alertas del Día"):
            requests.get(f"{API_URL}/alertas_fichaje/")
            st.toast("Alertas refrescadas")
        try:
            res_users_alert = requests.get(f"{API_URL}/usuarios/")
            # Busquemos un culpable.
            if res_users_alert.status_code == 200:
                u_list = {f"{u['nombre']} ({u['email']})": u['id'] for u in res_users_alert.json()}
                sospechoso = st.selectbox("Seleccionar sospechoso:", [""] + list(u_list.keys()))
                if sospechoso:
                    if st.button(f"🔍 Ver historial"):
                        r_hist = requests.get(f"{API_URL}/historial_alertas/{u_list[sospechoso]}")
                        if r_hist.status_code == 200 and r_hist.json():
                            st.table(pd.DataFrame(r_hist.json())[['fecha', 'motivo']])
        except:
            st.error("Error al cargar alertas.")

    with t4:
        # Burocracia y sentencias. El verdadero trabajo de un admin.
        st.header("📂 Gestión de Documentos y Sentencias")
        try:
            res_u_doc = requests.get(f"{API_URL}/usuarios/")
            if res_u_doc.status_code == 200:
                u_dict_doc = {f"{u['nombre']} ({u['email']})": u['id'] for u in res_u_doc.json()}
                # Un formulario para enviar archivos que probablemente nadie leerá.
                with st.expander("📤 Enviar nuevo archivo"):
                    with st.form("env_arch_form", clear_on_submit=True):
                        v_dest = st.selectbox("Destinatario:", list(u_dict_doc.keys()))
                        v_tit = st.text_input("Título:")
                        v_file = st.file_uploader("Archivo:", type=['pdf', 'docx', 'jpg', 'png'])
                        if st.form_submit_button("Lanzar Archivo"):
                            if v_file and v_tit and v_dest:
                                res_up = requests.post(f"{API_URL}/subir_documento/", 
                                                       data={"usuario_id": u_dict_doc[v_dest], "titulo": v_tit}, 
                                                       files={"archivo": (v_file.name, v_file.getvalue())})
                                if "error" in res_up.json(): st.error(f"Error: {res_up.json()['error']}")
                                else: st.success("Archivo enviado.")
        except:
            st.error("Error en gestión documental.")

        st.divider()
        # El chivato: ¿quién ha leído qué?
        try:
            r_ctrl = requests.get(f"{API_URL}/admin/documentos/")
            if r_ctrl.status_code == 200 and r_ctrl.json():
                st.table([{"Empleado": d.get("usuario_nombre"), "Doc": d.get("titulo"), "Leído": "✅ SÍ" if d.get("leido") else "❌ NO"} for d in r_ctrl.json()])
        except:
            # Si falla, disimulamos.
            st.write("Cargando chivatazos...")

        st.divider()
        # El tribunal de los preavisos. Aquí se decide el destino de los mortales.
        try:
            res_p_adm = requests.get(f"{API_URL}/admin/preavisos/")
            if res_p_adm.status_code == 200:
                p_pendientes = [p for p in res_p_adm.json() if p.get('estado') == 'pendiente']
                for p in p_pendientes:
                    # Para cada súplica, un par de botones: el pulgar arriba o el pulgar abajo.
                    id_p = p.get('id')
                    with st.container(border=True):
                        c_inf, c_btns = st.columns([3, 2])
                        c_inf.write(f"**{p.get('usuario_nombre')}** - {p.get('tipo')} ({p.get('fecha')})")
                        btn_ok, btn_no = c_btns.columns(2)
                        if btn_ok.button("✅ Aceptar", key=f"ok_{id_p}"):
                            if requests.post(f"{API_URL}/admin/decidir_preaviso/{id_p}", json={"estado": "aceptado"}).status_code == 200: st.rerun()
                        if btn_no.button("❌ Rechazar", key=f"no_{id_p}", type="primary"):
                            if requests.post(f"{API_URL}/admin/decidir_preaviso/{id_p}", json={"estado": "rechazado"}).status_code == 200: st.rerun()
        except:
            st.error("Error en preavisos.")