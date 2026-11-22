from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import RegistroConteo


class FlujoConteoTests(TestCase):
    def test_guardar_conteo_activo_y_consultarlo_en_historial(self):
        camara = SimpleNamespace(corriendo=True, cantidad=3, metodo="rostros")
        with patch("opcv.views.obtener_camara", return_value=camara):
            respuesta = self.client.post(reverse("api_guardar"))

        self.assertEqual(respuesta.status_code, 200)
        registro = RegistroConteo.objects.get(pk=respuesta.json()["id"])
        self.assertEqual((registro.cantidad, registro.metodo), (3, "rostros"))

        historial = self.client.get(reverse("api_historial")).json()
        self.assertEqual(historial["total"], 1)
        self.assertEqual(historial["registros"][0]["cantidad"], 3)
        self.assertEqual(historial["registros"][0]["metodo"], "rostros")

    def test_video_informa_error_si_la_fuente_no_abre(self):
        with patch("opcv.views.obtener_camara") as obtener_camara:
            camara = obtener_camara.return_value
            camara.iniciar.return_value = False
            camara.error = "No se pudo abrir la cámara."
            respuesta = self.client.get(reverse("video_feed"))

        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(respuesta.json(), {"error": "No se pudo abrir la cámara."})
