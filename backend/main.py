from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    email = Column(String, unique=True)
    password_hash = Column(String)
    rol = Column(String)

class Fichaje(Base):
    __tablename__ = "fichajes"
    id = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer)
    tipo = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    ip_origen = Column(String)
    dispositivo = Column(String)
    latitud = Column(String, nullable=True)
    longitud = Column(String, nullable=True)

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/usuarios/")
def listar_usuarios(db: Session = Depends(get_db)):
    return db.query(Usuario).all()

@app.get("/fichajes/{user_id}")
def obtener_fichajes(user_id: int, db: Session = Depends(get_db)):
    return db.query(Fichaje).filter(Fichaje.id_usuario == user_id).all()

@app.post("/fichar/{user_id}")
def crear_fichaje(
    user_id: int, 
    tipo: str, 
    lat: str = None, 
    lon: str = None, 
    db: Session = Depends(get_db)
):
    usuario = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    nuevo = Fichaje(
        id_usuario=user_id, 
        tipo=tipo, 
        ip_origen="127.0.0.1", 
        dispositivo="Web GPS",
        latitud=lat,
        longitud=lon
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return {"status": "ok", "fichaje": nuevo}

@app.post("/login")
def login(email: str, password: str, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == email).first()
    if not usuario or usuario.password_hash != password:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {"status": "ok", "user_id": usuario.id, "nombre": usuario.nombre, "rol": usuario.rol}
