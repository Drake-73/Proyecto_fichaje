from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import os
import time
from sqlalchemy.exc import OperationalError

# La URL de la base de datos. Si has tocado el compose y no coinciden, llorarás.
DATABASE_URL = "postgresql://admin_fichaje:password_muy_segura@db:5432/gestion_fichajes"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Definimos al "rebaño" (los usuarios)
class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    email = Column(String, unique=True)
    password_hash = Column(String)
    rol = Column(String, default="user") # 'admin' para los elegidos, 'user' para el resto

# Donde anotamos quién ha movido un dedo y dónde estaba (GPS)
class Fichaje(Base):
    __tablename__ = "fichajes"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    tipo = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    latitud = Column(Float)
    longitud = Column(Float)

# Intentamos despertar a la base de datos. Es lenta, como un lunes por la mañana.
for i in range(5):
    try:
        Base.metadata.create_all(bind=engine)
        break
    except OperationalError:
        time.sleep(5)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# Comprobamos si el usuario sabe escribir su propia clave
@app.post("/login")
def login(email: str, password: str, db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.email == email).first()
    if not user or user.password_hash != password:
        raise HTTPException(status_code=401, detail="Credenciales de chiste. Prueba otra vez.")
    return {"user_id": user.id, "nombre": user.nombre, "rol": user.rol}

# Guardamos el fichaje. El Gran Hermano te vigila.
@app.post("/fichar/{user_id}")
def fichar(user_id: int, tipo: str, lat: float, lon: float, db: Session = Depends(get_db)):
    nuevo = Fichaje(usuario_id=user_id, tipo=tipo, latitud=lat, longitud=lon)
    db.add(nuevo)
    db.commit()
    return {"status": "Fichado. Vuelve al tajo."}

@app.get("/fichajes/{user_id}")
def ver_fichajes(user_id: int, db: Session = Depends(get_db)):
    return db.query(Fichaje).filter(Fichaje.usuario_id == user_id).all()

@app.get("/usuarios/")
def listar_usuarios(db: Session = Depends(get_db)):
    return db.query(Usuario).all()

@app.post("/usuarios/")
def crear_usuario(nombre: str, email: str, password: str, rol: str = "user", db: Session = Depends(get_db)):
    nuevo = Usuario(nombre=nombre, email=email, password_hash=password, rol=rol)
    db.add(nuevo)
    db.commit()
    return {"status": "Súbdito creado con éxito."}
