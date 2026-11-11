import io
import json
import tempfile
import types
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

from nora import tools
from nora.assistant import AssistantService
from nora.cli import main


class CliTests(unittest.TestCase):
    def test_single_request_uses_needle(self):
        with patch('nora.cli.AssistantService') as service, redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()):
            service.return_value.ask.return_value = {'reply': 'Encontrado', 'sources': ['https://example.org']}
            self.assertEqual(main(['Pesquise', 'Cerrado']), 0)
            service.return_value._init_agent.assert_called_once()
            service.return_value.ask.assert_called_once_with('Pesquise Cerrado')
            self.assertIn('Fonte: https://example.org', output.getvalue())

    def test_model_failure_does_not_fall_back(self):
        with patch('nora.cli.AssistantService') as service, redirect_stderr(io.StringIO()) as error:
            service.return_value._init_agent.side_effect = RuntimeError('modelo indisponível')
            self.assertEqual(main(['Anote comprar café']), 1)
            service.return_value.ask.assert_not_called()
            self.assertIn('modelo indisponível', error.getvalue())

    def test_interactive_controls_and_request(self):
        with patch('nora.cli.AssistantService') as service, patch('builtins.input', side_effect=['/ajuda', '', 'Mostre minhas notas', '/sair']), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            service.return_value.ask.return_value = {'reply': 'Notas'}
            self.assertEqual(main([]), 0)
            service.return_value.ask.assert_called_once_with('Mostre minhas notas')

    def test_four_tools_registered_and_model_used(self):
        registered = []
        def tool(fn):
            registered.append(fn.__name__)
            return fn
        class FakeCactus:
            def __init__(self, **kwargs):
                self.options = kwargs
            def run(self, message, **kwargs):
                self.message = message
                return {'results': []}
        fake = types.SimpleNamespace(tool=tool, Cactus=FakeCactus)
        with patch.dict('sys.modules', cactus=fake):
            service = AssistantService()
            service.ask('Oi')
            self.assertEqual(service._agent.message, 'Oi')
            self.assertEqual(service._agent.options['generation'], 3)
        self.assertEqual(registered, ['buscar_wikipedia', 'consultar_clima', 'anotar', 'ver_anotacoes'])
        self.assertFalse(hasattr(tools, 'calcular'))

    def test_corrupt_notes_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'notes.json'
            path.write_text('{invalid', encoding='utf-8')
            with patch.object(tools, 'NOTES_FILE', path):
                with self.assertRaises(ValueError):
                    tools.salvar_nota('Não sobrescrever')
            self.assertEqual(path.read_text(encoding='utf-8'), '{invalid')
