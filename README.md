# 🚀 Sistema de Fichaje con Geolocalización GPS

Proyecto final para el ciclo de **ASIR**. Sistema de control de jornada laboral basado en microservicios con Docker.

## 🛠️ Tecnologías utilizadas
* **Backend:** FastAPI (Python) + SQLAlchemy.
* **Frontend:** Streamlit + Geolocation API.
* **Base de Datos:** PostgreSQL.
* **Despliegue:** Docker & Docker Compose.
* **Administración:** Adminer.

## ✨ Características
- 🔐 **Login seguro:** Acceso por email y contraseña.
- 📍 **Geolocalización:** Registro automático de latitud y longitud al fichar.
- 📊 **Panel Visual:** Historial con mapas interactivos de los fichajes.
- 📥 **Exportación:** Descarga de reportes en formato CSV para Excel.
- 🛡️ **Roles:** Diferenciación entre Usuario y Administrador.

## 🚀 Cómo desplegarlo
1. Clona el repositorio: `git clone https://github.com/TU_USUARIO/proyecto-fichaje.git`
2. Levanta los servicios: `docker-compose up -d --build`
3. Accede a la web: `http://localhost:8501`
