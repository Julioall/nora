"""CLI da NORA; todos os pedidos passam pelo Needle 3."""
from __future__ import annotations

import argparse
import sys

from .assistant import AssistantService


def _show(result: dict) -> None:
    print(result['reply'])
    for source in result.get('sources', []):
        print(f'Fonte: {source}')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='NORA — Wikipédia, clima e notas com Needle 3 local.')
    parser.add_argument('pedido', nargs='*', help='Pedido em linguagem natural; sem argumentos abre o modo interativo.')
    parser.add_argument('--camera', action='store_true', help='Observar webcam com Mirage e pesquisar com Needle 3.')
    parser.add_argument('--camera-id', type=int, default=0, help='Índice da webcam (padrão: 0).')
    parser.add_argument('--segundos', type=float, default=8, help='Período de observação, de 3 a 60 segundos.')
    parser.add_argument('--sem-preview', action='store_true', help='Usar câmera sem abrir a janela de vídeo.')
    args = parser.parse_args(argv)
    if not 3 <= args.segundos <= 60:
        parser.error('--segundos deve estar entre 3 e 60.')
    if args.camera and args.pedido:
        parser.error('Use --camera sem pedido de texto.')
    if args.camera:
        from .camera import run_camera
        try:
            return run_camera(args.camera_id, args.segundos, not args.sem_preview)
        except KeyboardInterrupt:
            print('\nCâmera encerrada.', file=sys.stderr)
            return 130
        except Exception as exc:
            print(f'Erro no modo câmera: {exc}', file=sys.stderr)
            return 1
    service = AssistantService()
    try:
        print('Carregando Needle 3 (o primeiro uso pode baixar o modelo)...', file=sys.stderr)
        service._init_agent()
        if args.pedido:
            _show(service.ask(' '.join(args.pedido)))
            return 0
        print('NORA pronta. Digite um pedido, /ajuda ou /sair.')
        while True:
            try:
                message = input('Você> ').strip()
            except EOFError:
                print()
                return 0
            if message == '/sair':
                return 0
            if message == '/ajuda':
                print('Exemplos: Pesquise Cerrado; Como está o clima em Goiânia?; '
                      'Anote comprar café; Mostre minhas notas. /sair para encerrar.')
                continue
            if message:
                try:
                    _show(service.ask(message))
                except Exception as exc:
                    print(f'Erro ao executar pedido: {exc}', file=sys.stderr)
    except KeyboardInterrupt:
        print('\nNORA encerrada.', file=sys.stderr)
        return 130
    except Exception as exc:
        print(f'Não foi possível executar a NORA: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
