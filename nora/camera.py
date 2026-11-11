"""Observação da webcam com Mirage, seguida de pesquisa via Needle 3."""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import time
import unicodedata

from . import tools


def identify(vision, rgb) -> str | None:
    # Português não consta dos idiomas documentados do Mirage. O termo em inglês
    # é pesquisado primeiro na Wikipédia pt, depois en, sem inventar tradução.
    result = vision.extract(rgb, {'object_name': {'type': 'string'}},
                            language='en', max_tokens=128)
    value = result.get('form', {}).get('object_name') if isinstance(result, dict) else None
    if isinstance(value, dict):
        value = value.get('value')
    if not isinstance(value, str):
        return None
    value = ' '.join(value.split()).strip(' ."')
    if not value or len(value) > 80 or value.casefold() in {'unknown', 'none', 'nothing', 'n/a', 'person', 'hand', 'face'}:
        return None
    return value


def consensus(observations: list[str | None]) -> tuple[str, int] | None:
    """Exige três votos e 70% das amostras, incluindo falhas de detecção."""
    valid = [unicodedata.normalize('NFKC', x).casefold() for x in observations if x]
    if not valid:
        return None
    label, count = Counter(valid).most_common(1)[0]
    if count < 3 or count / len(observations) < .7:
        return None
    return label, count


class CameraResearch:
    """Um agente Needle restrito à consulta, sem acesso a notas ou outras ações."""
    def __init__(self):
        import cactus

        @cactus.tool
        def buscar_wikipedia(assunto: str) -> dict:
            """Pesquisar na Wikipédia o nome do objeto observado.

            Args:
                assunto: nome do objeto copiado do pedido
            """
            result = tools.wikipedia(assunto)
            if not result.get('source'):
                result = tools.wikipedia(assunto, language='en')
            return result

        self._search_tool = buscar_wikipedia
        self.agent = cactus.Cactus(tools=[buscar_wikipedia], generation=3,
                                   system='locale: pt-BR; assistant: NORA; network: connected')

    def search(self, label: str) -> dict:
        # Uma única chamada proposta pelo Needle. Nunca executamos outra função
        # nem aceitamos um assunto diferente do candidato observado.
        self.agent.reset()
        result = self.agent.complete(f'Pesquise na Wikipédia: {label}', max_new_tokens=256)
        calls = result.get('function_calls', [])
        if not calls:
            return {'message': 'O Needle não selecionou uma pesquisa para essa observação.'}
        call = calls[0]
        subject = call.get('arguments', {}).get('assunto')
        if call.get('name') != 'buscar_wikipedia' or not isinstance(subject, str) or subject.casefold().strip() != label.casefold().strip():
            return {'message': 'O Needle não retornou uma consulta correspondente ao objeto observado.'}
        # A função só roda quando o modelo propõe a chamada válida.
        return self._search_tool(subject)


def _open_camera(cv2, index: int):
    """Prefer DirectShow on Windows; let OpenCV choose elsewhere."""
    if hasattr(cv2, 'CAP_DSHOW'):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if cap.isOpened():
            return cap
        cap.release()
    return cv2.VideoCapture(index)


def _panel(cv2, frame, state: str, label: str | None, details: str) :
    """Compose camera image above a readable result panel."""
    width = 900
    height = max(1, int(frame.shape[0] * width / frame.shape[1]))
    camera = cv2.resize(frame, (width, height))
    panel = __import__('numpy').full((250, width, 3), 28, dtype='uint8')
    cv2.putText(panel, state.upper(), (24, 34), cv2.FONT_HERSHEY_SIMPLEX, .7, (80, 210, 140), 2)
    heading = f'Identificação: {label or "aguardando objeto"}'
    cv2.putText(panel, heading[:72], (24, 74), cv2.FONT_HERSHEY_SIMPLEX, .65, (245, 245, 245), 2)
    # Wrap the model summary into lines that fit the fixed-width panel.
    words = details.replace('\n', ' ').split()
    lines, line = [], ''
    for word in words:
        candidate = (line + ' ' + word).strip()
        if len(candidate) > 98 and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    for i, text in enumerate(lines[:5]):
        cv2.putText(panel, text, (24, 112 + i * 27), cv2.FONT_HERSHEY_SIMPLEX, .52, (220, 220, 220), 1)
    return __import__('numpy').vstack((camera, panel))


def run_camera(index: int = 0, seconds: float = 8, preview: bool = True) -> int:
    try:
        import cv2
        import cactus
    except ImportError as exc:
        raise RuntimeError('Instale as dependências: python -m pip install -r requirements.txt') from exc

    print('Carregando Mirage e Needle 3...')
    vision = cactus.Mirage()
    research = CameraResearch()
    cap = _open_camera(cv2, index)
    pool = ThreadPoolExecutor(max_workers=1)
    pending = None
    title = 'NORA - camera (Q ou Esc para sair)'
    result_label = None
    result_text = 'Mostre um objeto no centro da imagem.'
    read_failures = 0
    try:
        if not cap.isOpened():
            raise RuntimeError(f'Não foi possível abrir a câmera {index}. Verifique a permissão e se outro programa está usando-a.')
        observations = []
        deadline = time.monotonic() + seconds
        next_sample = 0.0
        cooldown_until = 0.0
        last_label = None
        state = 'observando'
        print('Mostre um objeto no centro da câmera. Ctrl+C encerra; Q/Esc na janela também.')
        while True:
            ok, frame = cap.read()
            if not ok:
                read_failures += 1
                if preview:
                    canvas = _panel(cv2, __import__('numpy').zeros((360, 640, 3), dtype='uint8'), 'reconectando câmera', result_label, result_text)
                    cv2.imshow(title, canvas)
                    if cv2.waitKey(1) & 0xFF in (27, ord('q'), ord('Q')):
                        break
                if read_failures >= 8:
                    cap.release()
                    time.sleep(.5)
                    cap = _open_camera(cv2, index)
                    read_failures = 0
                    if not cap.isOpened():
                        result_text = 'Não consegui reabrir a câmera. Tentando novamente...'
                        time.sleep(1)
                else:
                    time.sleep(.15)
                continue
            read_failures = 0
            now = time.monotonic()
            height, width = frame.shape[:2]
            # Região central destacada: reduz interferência do fundo e da pessoa.
            x0, x1 = int(width * .2), int(width * .8)
            y0, y1 = int(height * .2), int(height * .8)
            if pending is not None and pending.done():
                job, pending = pending, None
                if state == 'pesquisando':
                    result = job.result()
                    result_label = last_label
                    result_text = result.get('message', 'Não houve resposta da pesquisa.')
                    print(result_text)
                    if result.get('source'):
                        print('Fonte:', result['source'])
                    else:
                        last_label = None
                    cooldown_until = now + 3
                    state = 'pausa'
                else:
                    label = job.result()
                    result_label = label
                    result_text = f'Observando: {label}' if label else 'Não consegui identificar o objeto neste quadro.'
                    observations.append(label)
                    print(f'Amostra {len(observations)}: {label or "sem identificação"}')
            if state == 'pausa' and now >= cooldown_until:
                observations = []
                deadline = now + seconds
                next_sample = now
                state = 'observando'
            if state == 'observando' and pending is None:
                if now >= deadline or len(observations) >= 12:
                    match = consensus(observations)
                    if match and match[0] != last_label:
                        last_label = match[0]
                        print(f'Parece ser: {last_label} ({match[1]}/{len(observations)} amostras). Pesquisando na Wikipédia...')
                        pending = pool.submit(research.search, last_label)
                        state = 'pesquisando'
                    else:
                        print('Mesmo objeto; aguardando mudança.' if match else 'Sem identificação consistente. Aproxime um único objeto e tente outro ângulo.')
                        if not match:
                            last_label = None
                        cooldown_until = now + 3
                        state = 'pausa'
                elif now >= next_sample:
                    crop = frame[y0:y1, x0:x1]
                    crop = cv2.resize(crop, (384, 384))
                    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                    pending = pool.submit(identify, vision, rgb)
                    next_sample = now + .8
            if preview:
                cv2.rectangle(frame, (x0, y0), (x1, y1), (0, 200, 0), 2)
                remaining = max(0, int(deadline - now))
                status = f'{state} {remaining if state == "observando" else ""}'
                cv2.imshow(title, _panel(cv2, frame, status, result_label, result_text))
                if cv2.waitKey(1) & 0xFF in (27, ord('q'), ord('Q')):
                    break
                if cv2.getWindowProperty(title, cv2.WND_PROP_VISIBLE) < 1:
                    break
            else:
                time.sleep(.02)
    finally:
        cap.release()
        if preview:
            cv2.destroyAllWindows()
        # Inferências nativas já iniciadas não são interrompidas à força.
        pool.shutdown(wait=True, cancel_futures=True)
    return 0
