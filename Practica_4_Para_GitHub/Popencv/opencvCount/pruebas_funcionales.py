"""Prueba HTTP del flujo de conteo con PostgreSQL y un video de una persona."""
import argparse
import csv
import json
import os
import time
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.request import HTTPCookieProcessor, Request, build_opener

URL = "http://127.0.0.1:8004"


def servir(video):
    from django.conf import settings
    from django.core.management import execute_from_command_line

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "opencvCount.settings")
    settings.CAMARA_FUENTE = str(video.resolve(strict=True))
    settings.METODO_DETECCION = "rostros"
    execute_from_command_line(
        ["manage.py", "runserver", "127.0.0.1:8004", "--noreload"]
    )


def probar(evidencias):
    evidencias.mkdir(parents=True, exist_ok=True)
    cookies = CookieJar()
    cliente = build_opener(HTTPCookieProcessor(cookies))

    def solicitar(ruta, csrf=None):
        if csrf is None:
            peticion = Request(URL + ruta)
        else:
            peticion = Request(
                URL + ruta, data=b"", headers={"X-CSRFToken": csrf}
            )
        return cliente.open(peticion, timeout=8)

    def leer_json(ruta, csrf=None):
        with solicitar(ruta, csrf) as respuesta:
            return json.load(respuesta)

    with solicitar("/") as pagina:
        html = pagina.read().decode("utf-8")
    assert "Iniciar cámara" in html and "Guardar registro" in html
    assert not leer_json("/api/conteo/")["activa"]
    assert leer_json("/api/historial/")["total"] == 0, "Usa una base vacía."
    csrf = next(cookie.value for cookie in cookies if cookie.name == "csrftoken")
    print("F01 OK | Página inicial y estado de espera")

    with solicitar("/video/") as video:
        assert video.headers.get_content_type() == "multipart/x-mixed-replace"
        assert video.readline().strip() == b"--frame"
        assert video.readline().strip() == b"Content-Type: image/jpeg"
        assert video.readline() == b"\r\n"
        jpeg = bytearray()
        while not jpeg.endswith(b"\xff\xd9"):
            byte = video.read(1)
            assert byte and len(jpeg) < 1024 * 1024, "Cuadro JPEG incompleto."
            jpeg.extend(byte)
        assert jpeg.startswith(b"\xff\xd8")
        (evidencias / "cuadro_deteccion.jpg").write_bytes(jpeg)

        for _ in range(20):
            estado = leer_json("/api/conteo/")
            if estado["activa"] and estado["personas"] == 1:
                break
            time.sleep(0.1)
        assert estado["activa"] and estado["personas"] == 1
        assert estado["metodo"] == "rostros"
        print("F02 OK | Flujo MJPEG y conteo de 1 persona")

        guardado = leer_json("/api/guardar/", csrf)
        assert guardado["cantidad"] == 1
        historial = leer_json("/api/historial/")
        assert historial["total"] == historial["maximo"] == historial["promedio"] == 1
        assert historial["registros"][0]["cantidad"] == 1
        print("F03 OK | Registro persistido y consultado en el historial")

        with solicitar("/exportar/") as descarga:
            assert descarga.headers.get_content_type() == "text/csv"
            contenido = descarga.read().decode("utf-8")
        filas = list(csv.DictReader(contenido.splitlines()))
        assert len(filas) == 1
        assert filas[0]["personas"] == "1" and filas[0]["metodo"] == "rostros"
        (evidencias / "conteo_personas.csv").write_text(contenido, encoding="utf-8")
        print("F04 OK | CSV con el registro de 1 persona")

        leer_json("/api/camara/detener/", csrf)
        assert not leer_json("/api/conteo/")["activa"]
        assert leer_json("/api/historial/")["total"] == 1
        print("F05 OK | Captura detenida y registro conservado")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--servir", type=Path, metavar="VIDEO")
    parser.add_argument("--evidencias", type=Path, default=Path("evidencias"))
    opciones = parser.parse_args()
    if opciones.servir:
        servir(opciones.servir)
    else:
        probar(opciones.evidencias)
