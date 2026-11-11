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
    args = parser.parse_args(argv)
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
