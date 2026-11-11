# NORA

Assistente de terminal em Python 3.12 com **Needle 3 obrigatório**. O modelo interpreta cada pedido em linguagem natural e escolhe entre quatro ferramentas:

- Pesquisar um resumo na Wikipédia em português.
- Consultar o clima atual de uma cidade com Open-Meteo.
- Salvar uma anotação local.
- Listar as últimas anotações.

Versão simplificada do projeto NORA_Needle3_Python312: interface web, servidor FastAPI, voz e calculadora foram removidos. Não há execução de comandos do sistema nem modo alternativo sem modelo. Needle é um modelo de seleção de ferramentas, não um chat de conversação livre.

## Instalar

Com Python 3.12 instalado, crie um ambiente virtual:

```bash
# Windows
py -3.12 -m venv .venv
.venv\Scripts\activate

# Linux/macOS
python3.12 -m venv .venv
source .venv/bin/activate
```

Depois de ativar o ambiente da sua plataforma:

```bash
python -m pip install -r requirements.txt
python -m nora
```

Opcionalmente, instale o comando curto com `python -m pip install -e .` e execute `nora`.

O primeiro pedido de execução carrega o Cactus/Needle 3 e pode baixar runtime e pesos. Se o modelo não carregar, o programa informa o erro e encerra; não usa regras para substituir a IA.

## Usar

```bash
python -m nora
python -m nora "Pesquise sobre o Cerrado"
python -m nora "Como está o clima em Goiânia?"
python -m nora "Anote preparar a webaula de amanhã"
python -m nora "Mostre minhas notas"
```

No modo interativo, `/ajuda` mostra exemplos e `/sair` encerra. Esses controles do terminal não consultam o modelo. Pedidos aceitam até 700 caracteres. Cada pedido é independente, sem histórico de conversa. Respostas vêm dos dados das ferramentas, incluindo a fonte quando disponível.

Wikipédia e clima precisam de internet. Notas são salvas em `~/.nora/notes.json` (pasta do usuário), com até 100 registros; a listagem mostra os últimos 10. Para outro caminho, defina `NORA_NOTES_FILE` antes de iniciar. Use uma instância por arquivo de notas. Um arquivo inválido gera erro em vez de ser sobrescrito.

## Testes

```bash
python -m unittest discover -s tests -v
```

Os testes usam um agente e APIs simulados: validam o CLI, o encaminhamento ao Needle e as ferramentas sem baixar o modelo. A inferência real depende do runtime Cactus e dos pesos disponíveis no computador; não foi homologada nesta adaptação.

Código principal: `nora/cli.py` (terminal), `nora/assistant.py` (Needle 3), `nora/tools.py` (funções). A integração Cactus foi preservada do projeto original.

## Referências

- [Cactus / Needle 3](https://huggingface.co/Cactus-Compute/needle3)
- [API Python do Cactus](https://www.cactuscompute.com/blog/needle-python-docs)
- [MediaWiki API](https://www.mediawiki.org/wiki/API:Main_page)
- [Open-Meteo](https://open-meteo.com/)

Licença MIT; dependências e serviços externos possuem seus próprios termos.
