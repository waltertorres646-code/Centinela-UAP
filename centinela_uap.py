#!/usr/bin/env python3
"""Centinela UAP: observador local y de solo lectura para publicaciones públicas.

No publica, no comenta, no modera y no descarga archivos multimedia.
Si Reddit indica que una publicación fue eliminada o retirada, purga su contenido
local y conserva únicamente identificadores, fechas, estado y huella SHA-256.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import praw
except ImportError:
    print("Falta PRAW. Ejecuta INSTALAR_Y_PROBAR.bat.", file=sys.stderr)
    raise SystemExit(2)


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "datos" / "centinela_uap.sqlite3"
CSV_PATH = BASE_DIR / "datos" / "publicaciones_uap.csv"
ENV_PATH = BASE_DIR / ".env"

# Son indicadores de revisión, no pruebas de espionaje ni de origen extraordinario.
PALABRAS_ALERTA = {
    "espionaje",
    "spy",
    "surveillance",
    "military",
    "militar",
    "radar",
    "sensor",
    "nuclear",
    "navy",
    "air force",
}


def traducir_bloques(texto: str, traducir: Any, maximo: int = 2500) -> str:
    """Traduce por bloques para no saturar el modelo local."""
    if not texto:
        return ""
    bloques: list[str] = []
    actual = ""
    for parrafo in texto.splitlines() or [texto]:
        if len(actual) + len(parrafo) + 1 <= maximo:
            actual = f"{actual}\n{parrafo}".strip()
            continue
        if actual:
            bloques.append(actual)
        while len(parrafo) > maximo:
            bloques.append(parrafo[:maximo])
            parrafo = parrafo[maximo:]
        actual = parrafo
    if actual:
        bloques.append(actual)
    return "\n".join(traducir(bloque) for bloque in bloques)


def traducir_al_espanol(titulo: str, texto: str) -> tuple[str, str]:
    """Traduce EN→ES localmente; ante cualquier problema conserva el original."""
    contenido = f"{titulo}\n{texto}".strip()
    if not contenido:
        return "", ""
    try:
        from langdetect import DetectorFactory, detect
        from argostranslate import translate

        DetectorFactory.seed = 0
        muestra = contenido[:4000]
        if len(muestra) >= 20 and detect(muestra) != "en":
            return "", ""
        idiomas = {idioma.code: idioma for idioma in translate.get_installed_languages()}
        traduccion = idiomas["en"].get_translation(idiomas["es"])
        return (
            traducir_bloques(titulo, traduccion.translate),
            traducir_bloques(texto, traduccion.translate),
        )
    except Exception:
        return "", ""


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cargar_env(path: Path) -> None:
    """Carga KEY=VALUE sin imprimir secretos ni sobrescribir el entorno."""
    if not path.exists():
        return
    for linea in path.read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if clave:
            os.environ.setdefault(clave, valor)


def credenciales() -> tuple[str, str, str]:
    cargar_env(ENV_PATH)
    valores = (
        os.getenv("REDDIT_CLIENT_ID", "").strip(),
        os.getenv("REDDIT_CLIENT_SECRET", "").strip(),
        os.getenv("REDDIT_USER_AGENT", "").strip(),
    )
    if not all(valores) or any(v.startswith("PON_AQUI") for v in valores):
        raise RuntimeError(
            "Faltan datos en .env. Completa REDDIT_CLIENT_ID, "
            "REDDIT_CLIENT_SECRET y REDDIT_USER_AGENT."
        )
    return valores


def conectar_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS publicaciones (
            id TEXT PRIMARY KEY,
            subreddit TEXT NOT NULL,
            titulo TEXT,
            titulo_es TEXT,
            autor TEXT,
            texto TEXT,
            texto_es TEXT,
            url TEXT,
            permalink TEXT NOT NULL,
            creado_utc TEXT NOT NULL,
            flair TEXT,
            puntaje INTEGER,
            comentarios INTEGER,
            primera_vista TEXT NOT NULL,
            ultima_vista TEXT NOT NULL,
            estado TEXT NOT NULL,
            huella_sha256 TEXT,
            alertas TEXT
        );
        CREATE TABLE IF NOT EXISTS observaciones (
            numero INTEGER PRIMARY KEY AUTOINCREMENT,
            id_publicacion TEXT NOT NULL,
            observado_en TEXT NOT NULL,
            estado TEXT NOT NULL,
            huella_sha256 TEXT,
            FOREIGN KEY(id_publicacion) REFERENCES publicaciones(id)
        );
        CREATE INDEX IF NOT EXISTS idx_observaciones_id
            ON observaciones(id_publicacion);
        """
    )
    columnas = {fila[1] for fila in db.execute("PRAGMA table_info(publicaciones)")}
    if "titulo_es" not in columnas:
        db.execute("ALTER TABLE publicaciones ADD COLUMN titulo_es TEXT")
    if "texto_es" not in columnas:
        db.execute("ALTER TABLE publicaciones ADD COLUMN texto_es TEXT")
    return db


def limpiar(valor: Any) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def estado_de(post: Any) -> str:
    titulo = limpiar(getattr(post, "title", "")).lower()
    texto = limpiar(getattr(post, "selftext", "")).lower()
    autor = getattr(post, "author", None)
    if titulo == "[deleted]" or texto == "[deleted]" or autor is None:
        return "eliminada"
    if texto == "[removed]" or getattr(post, "removed_by_category", None):
        return "retirada"
    return "publica"


def datos_post(post: Any, subreddit: str) -> dict[str, Any]:
    titulo = limpiar(getattr(post, "title", ""))
    texto = limpiar(getattr(post, "selftext", ""))
    url = limpiar(getattr(post, "url", ""))
    autor_obj = getattr(post, "author", None)
    autor = limpiar(autor_obj) if autor_obj is not None else ""
    estado = estado_de(post)
    creado = datetime.fromtimestamp(
        float(post.created_utc), tz=timezone.utc
    ).isoformat(timespec="seconds")
    contenido = {
        "id": post.id,
        "titulo": titulo,
        "autor": autor,
        "texto": texto,
        "url": url,
        "creado_utc": creado,
    }
    huella = hashlib.sha256(
        json.dumps(contenido, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    alertas = sorted(
        palabra
        for palabra in PALABRAS_ALERTA
        if palabra in f"{titulo}\n{texto}".lower()
    )
    titulo_es, texto_es = traducir_al_espanol(titulo, texto)

    # Purga preventiva al recibir una señal de eliminación o retirada.
    if estado != "publica":
        titulo = titulo_es = autor = texto = texto_es = url = ""
        alertas = []

    return {
        "id": post.id,
        "subreddit": subreddit,
        "titulo": titulo,
        "titulo_es": titulo_es,
        "autor": autor,
        "texto": texto,
        "texto_es": texto_es,
        "url": url,
        "permalink": f"https://www.reddit.com{post.permalink}",
        "creado_utc": creado,
        "flair": limpiar(getattr(post, "link_flair_text", "")),
        "puntaje": int(getattr(post, "score", 0) or 0),
        "comentarios": int(getattr(post, "num_comments", 0) or 0),
        "estado": estado,
        "huella_sha256": huella,
        "alertas": ", ".join(alertas),
    }


def guardar(db: sqlite3.Connection, datos: dict[str, Any]) -> bool:
    instante = ahora_iso()
    anterior = db.execute(
        "SELECT estado, huella_sha256 FROM publicaciones WHERE id = ?",
        (datos["id"],),
    ).fetchone()
    es_nueva = anterior is None
    cambio = es_nueva or anterior["estado"] != datos["estado"] or (
        datos["estado"] == "publica"
        and anterior["huella_sha256"] != datos["huella_sha256"]
    )

    db.execute(
        """
        INSERT INTO publicaciones (
            id, subreddit, titulo, titulo_es, autor, texto, texto_es, url,
            permalink, creado_utc,
            flair, puntaje, comentarios, primera_vista, ultima_vista, estado,
            huella_sha256, alertas
        ) VALUES (
            :id, :subreddit, :titulo, :titulo_es, :autor, :texto, :texto_es,
            :url, :permalink, :creado_utc, :flair, :puntaje, :comentarios, :primera_vista,
            :ultima_vista, :estado, :huella_sha256, :alertas
        )
        ON CONFLICT(id) DO UPDATE SET
            subreddit=excluded.subreddit,
            titulo=excluded.titulo,
            titulo_es=excluded.titulo_es,
            autor=excluded.autor,
            texto=excluded.texto,
            texto_es=excluded.texto_es,
            url=excluded.url,
            permalink=excluded.permalink,
            flair=excluded.flair,
            puntaje=excluded.puntaje,
            comentarios=excluded.comentarios,
            ultima_vista=excluded.ultima_vista,
            estado=excluded.estado,
            huella_sha256=CASE
                WHEN excluded.estado = 'publica' THEN excluded.huella_sha256
                ELSE publicaciones.huella_sha256
            END,
            alertas=excluded.alertas
        """,
        {**datos, "primera_vista": instante, "ultima_vista": instante},
    )
    if cambio:
        db.execute(
            """
            INSERT INTO observaciones
                (id_publicacion, observado_en, estado, huella_sha256)
            VALUES (?, ?, ?, ?)
            """,
            (datos["id"], instante, datos["estado"], datos["huella_sha256"]),
        )
    return es_nueva


def exportar_csv(db: sqlite3.Connection) -> None:
    filas = db.execute(
        """
        SELECT id, subreddit, titulo, titulo_es, autor, texto_es, url, permalink,
               creado_utc, flair,
               puntaje, comentarios, primera_vista, ultima_vista, estado,
               huella_sha256, alertas
        FROM publicaciones
        ORDER BY creado_utc DESC
        """
    ).fetchall()
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(filas[0].keys() if filas else [
            "id", "subreddit", "titulo", "titulo_es", "autor", "texto_es",
            "url", "permalink",
            "creado_utc", "flair", "puntaje", "comentarios",
            "primera_vista", "ultima_vista", "estado", "huella_sha256",
            "alertas",
        ])
        escritor.writerows([tuple(fila) for fila in filas])


def escanear(reddit: Any, subreddit: str, limite: int) -> tuple[int, int]:
    nuevas = 0
    revisadas = 0
    with conectar_db() as db:
        for post in reddit.subreddit(subreddit).new(limit=limite):
            datos = datos_post(post, subreddit)
            nuevas += int(guardar(db, datos))
            revisadas += 1
            marca = "ALERTA" if datos["alertas"] else datos["estado"].upper()
            titulo_visible = datos["titulo_es"] or datos["titulo"]
            print(f"[{marca}] {datos['id']} | {titulo_visible[:75]}")
        exportar_csv(db)
    return revisadas, nuevas


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Observa publicaciones públicas de Reddit sin publicar nada."
    )
    parser.add_argument("--subreddit", default="UFOs", help="Nombre sin r/")
    parser.add_argument("--limite", type=int, default=25, choices=range(1, 101))
    parser.add_argument("--vigilar", action="store_true", help="Repite el escaneo")
    parser.add_argument("--cada", type=int, default=300, help="Segundos entre escaneos")
    return parser.parse_args()


def main() -> int:
    args = argumentos()
    if args.cada < 60:
        print("Por respeto a la API, --cada no puede ser menor de 60 segundos.")
        return 2
    try:
        client_id, client_secret, user_agent = credenciales()
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            check_for_async=False,
        )
        if not reddit.read_only:
            raise RuntimeError("La conexión no quedó en modo de solo lectura.")
        while True:
            revisadas, nuevas = escanear(reddit, args.subreddit, args.limite)
            print(
                f"{ahora_iso()} | Revisadas: {revisadas} | Nuevas: {nuevas} | "
                f"CSV: {CSV_PATH}"
            )
            if not args.vigilar:
                return 0
            time.sleep(args.cada)
    except KeyboardInterrupt:
        print("\nCentinela detenido correctamente.")
        return 0
    except Exception as exc:
        print(f"No se pudo completar el escaneo: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
