"""Testes que não exigem o download do modelo ou acesso à internet."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nora import tools
from nora.assistant import AssistantService


class ToolTests(unittest.TestCase):
    def test_notas_persistentes(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(tools, "NOTES_FILE", Path(folder) / "notes.json"):
                self.assertIn("não tem anotações", tools.listar_notas()["message"])
                result = tools.salvar_nota("comprar livros")
                self.assertIn("Anotação salva", result["message"])
                self.assertIn("comprar livros", tools.listar_notas()["message"])

    def test_wikipedia_com_api_simulada(self):
        calls = [
            {"query": {"search": [{"title": "Cerrado"}]}},
            {"query": {"pages": [{"title": "Cerrado", "extract": "O Cerrado é um bioma brasileiro."}]}},
        ]
        with patch.object(tools, "_get_json", side_effect=calls):
            result = tools.wikipedia("Cerrado")
        self.assertIn("bioma brasileiro", result["message"])
        self.assertEqual(result["source"], "https://pt.wikipedia.org/wiki/Cerrado")

    def test_clima_com_api_simulada(self):
        calls = [
            {"results": [{"name": "Goiânia", "admin1": "Goiás", "country": "Brasil", "latitude": -16.7, "longitude": -49.2}]},
            {"current": {"temperature_2m": 28.4, "apparent_temperature": 30.1, "relative_humidity_2m": 55, "weather_code": 2, "wind_speed_10m": 12.0}},
        ]
        with patch.object(tools, "_get_json", side_effect=calls):
            result = tools.clima("Goiânia")
        self.assertIn("28.4 °C", result["message"])
        self.assertIn("parcialmente nublado", result["message"])

    def test_resposta_do_agente(self):
        class FakeAgent:
            def run(self, text, **kwargs):
                return {"results": [{"kind": "wikipedia", "message": "Resumo encontrado", "source": "https://pt.wikipedia.org/wiki/Cerrado"}]}
        service = AssistantService()
        with patch.object(service, "_init_agent", return_value=FakeAgent()):
            result = service.ask("Pesquise Cerrado")
        self.assertEqual(result["reply"], "Resumo encontrado")
        self.assertEqual(result["tools_used"], ["wikipedia"])

    def test_fora_do_escopo(self):
        class FakeAgent:
            def run(self, text, **kwargs):
                return {"results": []}
        service = AssistantService()
        with patch.object(service, "_init_agent", return_value=FakeAgent()):
            result = service.ask("Crie um programa complexo em C++")
        self.assertIn("Ainda não tenho uma ferramenta", result["reply"])


if __name__ == "__main__":
    unittest.main()
