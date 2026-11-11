"""Projeto 171: eventos visíveis por área de mesa, sem identificação pessoal."""
from __future__ import annotations

import csv
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from .camera import _open_camera, detect, draw_detections

PEOPLE = {'person', 'man', 'woman', 'boy', 'girl', 'human', 'student'}
PHONES = {'phone', 'cell phone', 'mobile phone', 'smartphone', 'cellphone', 'telephone'}


def center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def inside(point, box):
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def observations(objects, zones):
    """Associate a person's center with one desk; phone must overlap that person."""
    people = [o for o in objects if o['name'].casefold().strip() in PEOPLE]
    phones = [o for o in objects if o['name'].casefold().strip() in PHONES]
    result = {z['name']: {'occupied': False, 'phone': False} for z in zones}
    for person in people:
        matches = [z for z in zones if inside(center(person['bbox']), z['bbox'])]
        if not matches:
            continue
        zone = min(matches, key=lambda z: sum((a-b)**2 for a, b in zip(center(z['bbox']), center(person['bbox']))))
        state = result[zone['name']]
        state['occupied'] = True
        state['phone'] |= any(inside(center(phone['bbox']), person['bbox']) for phone in phones)
    return result


class Events:
    """Debounced changes. Missing detection is explicitly an apparent departure."""
    def __init__(self, zones, emit, dwell=4.):
        self.emit, self.dwell = emit, dwell
        self.states = {z['name']: {'occupied': None, 'phone': False} for z in zones}
        self.pending = {}
        self.last_sample = None

    def update(self, values, now):
        # Do not bridge a capture/inference gap and call it a continuous event.
        if self.last_sample is not None and now - self.last_sample > max(10., self.dwell * 2):
            self.pending.clear()
            for state in self.states.values():
                state['occupied'] = None
                state['phone'] = False
            self.emit('sistema', 'intervalo_sem_observacao', 0)
        self.last_sample = now
        for name, sample in values.items():
            for key in ('occupied', 'phone'):
                value = sample[key]
                old = self.states[name][key]
                token = (name, key)
                if old == value:
                    self.pending.pop(token, None)
                    continue
                previous = self.pending.get(token)
                if previous is None or previous[0] != value:
                    self.pending[token] = (value, now, 1)
                    continue
                self.pending[token] = (value, previous[1], previous[2] + 1)
                if now - previous[1] < self.dwell or previous[2] < 1:
                    continue
                self.states[name][key] = value
                self.pending.pop(token, None)
                if key == 'occupied':
                    # Initial empty seats are not departures.
                    if old is not None:
                        self.emit(name, 'retorno_aparente' if value else 'saida_aparente', now)
                    elif value:
                        self.emit(name, 'ocupacao_inicial', now)
                elif value:
                    self.emit(name, 'telefone_junto_a_pessoa', now)
                else:
                    self.emit(name, 'telefone_nao_mais_detectado', now)


def run_classroom(index=0, output=None):
    import cv2
    import cactus
    import numpy as np

    folder = Path(output) if output else Path.home() / '.nora' / 'sessoes' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    folder.mkdir(parents=True, exist_ok=True)
    title = 'Projeto 171 - ENTER iniciar | R relatorio | Q sair'
    cap = _open_camera(cv2, index)
    pool = ThreadPoolExecutor(max_workers=1)
    job = None
    zones, clicks, objects, log = [], [], [], []
    active, latest = False, 'Marque dois cantos da area ocupada por cada aluno sentado.'
    tracker = None
    report_requested = False
    next_sample = 0.
    stream = None
    try:
        if not cap.isOpened():
            raise RuntimeError('Câmera indisponível. Feche outros programas que usam a webcam.')
        stream = (folder / 'eventos.csv').open('w', encoding='utf-8-sig', newline='')
        writer = csv.DictWriter(stream, fieldnames=['horario', 'mesa', 'evento', 'duracao_aproximada_s'], delimiter=';')
        writer.writeheader()
        starts = {}

        def emit(name, event, now):
            duration = 0.
            if event in {'saida_aparente', 'telefone_junto_a_pessoa'}:
                starts[(name, event)] = now
            closing = {'retorno_aparente': 'saida_aparente', 'telefone_nao_mais_detectado': 'telefone_junto_a_pessoa'}
            if event in closing:
                started = starts.pop((name, closing[event]), None)
                duration = round(now - started, 1) if started is not None else 0.
            if event == 'intervalo_sem_observacao':
                starts.clear()
            entry = dict(horario=datetime.now().astimezone().isoformat(timespec='seconds'), mesa=name,
                         evento=event, duracao_aproximada_s=duration)
            log.append(entry)
            writer.writerow(entry)
            stream.flush()

        print('Carregando Mirage e Needle 3...')
        vision = cactus.Mirage()

        @cactus.tool
        def gerar_relatorio() -> dict:
            """Gerar o relatório dos eventos observados na sessão de aula."""
            counts = Counter(row['evento'] for row in log)
            data = {'proposta': 'Explorar novas formas de acompanhar a participação e melhorar estratégias pedagógicas.',
                    'limites': 'Eventos aparentes por mesa. Ausência de detecção não comprova saída; telefone próximo não comprova uso. Sem inferência de atenção.',
                    'mesas': zones, 'contagens': dict(counts), 'eventos': list(log),
                    'eventos_ainda_abertos': [{'mesa': key[0], 'evento': key[1]} for key in starts]}
            path = folder / 'relatorio.json'
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            return {'message': f'Relatório salvo: {path}'}

        agent = cactus.Cactus(tools=[gerar_relatorio], generation=3)

        def report():
            agent.reset()
            response = agent.complete('Gerar relatório dos eventos observados na sessão de aula.')
            if any(c.get('name') == 'gerar_relatorio' for c in response.get('function_calls', [])):
                return gerar_relatorio()['message']
            return 'Needle não selecionou o relatório. O CSV de eventos continua salvo.'

        def mouse(event, x, y, flags, params):
            if active or y >= 506 or event != cv2.EVENT_LBUTTONDOWN:
                return
            clicks.append((x / 900 * 1000, y / 506 * 1000))
            if len(clicks) == 2:
                a, b = clicks
                box = [min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])]
                if box[2] - box[0] >= 10 and box[3] - box[1] >= 10:
                    zones.append({'name': f'Mesa {len(zones)+1}', 'bbox': box})
                clicks.clear()

        cv2.namedWindow(title)
        cv2.setMouseCallback(title, mouse)
        failures = 0
        while True:
            ok, frame = cap.read()
            now = time.monotonic()
            if not ok:
                failures += 1
                latest = 'Sem quadros da camera. Tentando reconectar...'
                frame = np.zeros((506, 900, 3), dtype='uint8')
                if failures % 15 == 0:
                    cap.release()
                    cap = _open_camera(cv2, index)
                time.sleep(.05)
            else:
                failures = 0
                if job is not None and job.done():
                    try:
                        objects = job.result()
                        tracker.update(observations(objects, zones), now)
                    except Exception as exc:
                        latest = f'Falha de observacao: {exc}'
                    job = None
                if active and job is None and not report_requested and now >= next_sample:
                    job = pool.submit(detect, vision, cv2.cvtColor(frame.copy(), cv2.COLOR_BGR2RGB))
                    next_sample = now + .8
            display = cv2.resize(frame, (900, 506))
            draw_detections(cv2, display, objects)
            for zone in zones:
                x0,y0,x1,y1 = zone['bbox']
                color = (80, 220, 100)
                state = tracker.states[zone['name']] if tracker else {}
                if state.get('phone'):
                    color = (60, 180, 250)
                elif state.get('occupied') is False:
                    color = (200, 160, 80)
                cv2.rectangle(display, (int(x0*.9),int(y0*.506)), (int(x1*.9),int(y1*.506)), color, 2)
                cv2.putText(display, zone['name'], (int(x0*.9),max(20,int(y0*.506))), cv2.FONT_HERSHEY_SIMPLEX,.55,color,2)
            panel = np.full((100,900,3),25,dtype='uint8')
            cv2.putText(panel, 'Monitorando eventos visiveis' if active else 'Calibracao: 2 cliques por mesa; U desfaz; ENTER inicia', (12,28), cv2.FONT_HERSHEY_SIMPLEX,.55,(230,230,230),1)
            cv2.putText(panel, latest[:105], (12,58),cv2.FONT_HERSHEY_SIMPLEX,.45,(220,220,220),1)
            cv2.putText(panel, f'{len(log)} eventos | R exporta | Q encerra', (12,85),cv2.FONT_HERSHEY_SIMPLEX,.5,(220,220,220),1)
            cv2.imshow(title,np.vstack((display,panel)))
            key = cv2.waitKey(1) & 0xff
            if key in (27,ord('q')) or cv2.getWindowProperty(title,cv2.WND_PROP_VISIBLE)<1:
                break
            if key == ord('u') and not active:
                if clicks: clicks.clear()
                elif zones: zones.pop()
            if key in (10,13) and zones and not active:
                tracker = Events(zones,emit)
                active = True
                latest = 'Observando mesas. Telefone junto a pessoa e saida sao eventos aparentes.'
                (folder/'mesas.json').write_text(json.dumps(zones,ensure_ascii=False,indent=2),encoding='utf-8')
            if key == ord('r'):
                report_requested = True
            if report_requested and job is None:
                latest = report()
                report_requested = False
        print(report())
    finally:
        cap.release()
        cv2.destroyAllWindows()
        pool.shutdown(wait=True,cancel_futures=True)
        if stream:
            stream.close()
        print(f'Eventos locais: {folder}')
    return 0
