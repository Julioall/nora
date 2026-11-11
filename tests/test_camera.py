import io
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import Mock, patch

from nora.camera import identify, consensus, CameraResearch, run_camera
from nora.cli import main


class CameraTests(unittest.TestCase):
    def test_temporal_consensus_includes_misses_and_rejects_ties(self):
        self.assertEqual(consensus(['Mug', 'mug', 'mug', None]), ('mug', 3))
        self.assertIsNone(consensus(['mug', 'mug']))
        self.assertIsNone(consensus(['mug', 'mug', 'mug', None, None]))
        self.assertIsNone(consensus(['mug', 'mug', 'book', 'book']))
        self.assertIsNone(consensus([None, None]))

    def test_visual_form_uses_rgb_and_english(self):
        vision = Mock()
        vision.extract.return_value = {'form': {'object_name': 'Coffee mug'}}
        pixels = object()
        self.assertEqual(identify(vision, pixels), 'Coffee mug')
        self.assertIs(vision.extract.call_args.args[0], pixels)
        self.assertEqual(vision.extract.call_args.kwargs['language'], 'en')
        for value in ['unknown', '', 'person', 'a' * 81, None]:
            vision.extract.return_value = {'form': {'object_name': value}}
            self.assertIsNone(identify(vision, pixels))

    def research(self, call):
        agent = Mock()
        agent.complete.return_value = {'function_calls': call}
        fake = types.SimpleNamespace(tool=lambda fn: fn, Cactus=Mock(return_value=agent))
        with patch.dict('sys.modules', cactus=fake):
            return CameraResearch(), agent

    def test_needle_required_before_wikipedia_and_english_fallback(self):
        service, agent = self.research([{'name': 'buscar_wikipedia', 'arguments': {'assunto': 'mug'}}])
        with patch('nora.camera.tools.wikipedia', side_effect=[{'message': 'Não encontrado'}, {'source': 'https://en.wikipedia.org/wiki/Mug', 'message': 'A mug is...'}]) as wiki:
            result = service.search('mug')
        agent.reset.assert_called_once()
        agent.complete.assert_called_once()
        self.assertEqual(wiki.call_count, 2)
        self.assertEqual(wiki.call_args.kwargs, {'language': 'en'})
        self.assertIn('source', result)

    def test_no_lookup_if_needle_refuses_or_changes_subject(self):
        for calls in [[], [{'name': 'anotar', 'arguments': {'assunto': 'mug'}}], [{'name': 'buscar_wikipedia', 'arguments': {'assunto': 'book'}}]]:
            service, _ = self.research(calls)
            with patch('nora.camera.tools.wikipedia') as wiki:
                service.search('mug')
                wiki.assert_not_called()

    def test_camera_arguments_dispatch(self):
        with patch('nora.camera.run_camera', return_value=0) as camera:
            self.assertEqual(main(['--camera', '--segundos', '10', '--camera-id', '1', '--sem-preview']), 0)
            camera.assert_called_once_with(1, 10, False)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['--camera', '--segundos', 'nan'])

    def test_camera_released_if_unavailable(self):
        cap = Mock()
        cap.isOpened.return_value = False
        cv = types.SimpleNamespace(VideoCapture=Mock(return_value=cap), destroyAllWindows=Mock())
        cactus = types.SimpleNamespace(Mirage=Mock())
        with patch.dict('sys.modules', cv2=cv, cactus=cactus), patch('nora.camera.CameraResearch'), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'abrir a câmera'):
                run_camera()
        cap.release.assert_called_once()
        cv.destroyAllWindows.assert_called_once()

    def test_live_loop_observes_researches_and_does_not_repeat_same_object(self):
        from concurrent.futures import Future
        class InlinePool:
            def __init__(self, **kwargs):
                pass
            def submit(self, function, *args):
                future = Future()
                future.set_result(function(*args))
                return future
            def shutdown(self, **kwargs):
                pass
        # A MagicMock supports image slicing without NumPy/OpenCV installed.
        from unittest.mock import MagicMock
        frame = MagicMock()
        frame.shape = (480, 640, 3)
        cap = Mock()
        cap.isOpened.return_value = True
        cap.read.return_value = (True, frame)
        cv = Mock()
        cv.VideoCapture.return_value = cap
        cv.waitKey.side_effect = [0] * 28 + [ord('q')]
        cv.getWindowProperty.return_value = 1
        ticks = iter(x * .5 for x in range(100))
        research = Mock()
        research.search.return_value = {'message': 'Uma caneca é...', 'source': 'https://pt.wikipedia.org/wiki/Caneca'}
        cactus = types.SimpleNamespace(Mirage=Mock())
        with patch.dict('sys.modules', cv2=cv, cactus=cactus), patch('nora.camera.CameraResearch', return_value=research), patch('nora.camera.identify', return_value='mug') as identify_mock, patch('nora.camera.ThreadPoolExecutor', InlinePool), patch('nora.camera.time.monotonic', side_effect=lambda: next(ticks)), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(run_camera(seconds=3), 0)
        self.assertGreaterEqual(identify_mock.call_count, 3)
        research.search.assert_called_once_with('mug')
        self.assertIn('Parece ser: mug', output.getvalue())
        self.assertIn('Uma caneca é...', output.getvalue())
        cap.release.assert_called_once()
