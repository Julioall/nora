# NORA

Assistente de terminal em Python 3.12 com **Needle 3 obrigatório** e modo webcam com Mirage. O modelo interpreta cada pedido em linguagem natural e escolhe entre quatro ferramentas:

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

Código principal: `nora/camera.py` (webcam + Mirage + Needle), `nora/cli.py` (terminal), `nora/assistant.py` (Needle 3), `nora/tools.py` (funções). A integração Cactus foi preservada do projeto original.

## Referências

- [Cactus / Needle 3](https://huggingface.co/Cactus-Compute/needle3)
- [API Python do Cactus](https://www.cactuscompute.com/blog/needle-python-docs)
- [MediaWiki API](https://www.mediawiki.org/wiki/API:Main_page)
- [Open-Meteo](https://open-meteo.com/)

Licença MIT; dependências e serviços externos possuem seus próprios termos.


## Mostrar um objeto na câmera

Atualize as dependências e inicie:

```bash
python -m pip install -r requirements.txt
python -m nora --camera
```

Uma janela nativa mostra a webcam e um retângulo central. Coloque **um objeto dentro do retângulo**, com boa iluminação. A NORA:

1. Observa durante aproximadamente 8 segundos, analisando uma amostra a cada 0,8 segundo no máximo (até 12 amostras por ciclo).
2. Usa **Mirage** para extrair o nome do objeto de cada imagem central.
3. Exige pelo menos 3 amostras com o mesmo nome e concordância em 70% das amostras, contando também as tentativas sem identificação. Essa medida é consistência temporal, não probabilidade de acerto.
4. Apresenta “Parece ser…” e envia o candidato ao **Needle 3**, com acesso somente à ferramenta de pesquisa. A pesquisa só roda se o Needle selecionar essa ferramenta com o mesmo termo observado.
5. Mostra o resumo da Wikipédia e o link no terminal. Depois de uma pausa de 3 segundos, começa outra observação. Uma consulta bem-sucedida não se repete enquanto o mesmo objeto continuar sendo reconhecido; uma mudança ou ciclo sem consenso libera uma nova consulta.

**Q**, **Esc**, fechar a janela ou **Ctrl+C** encerra e libera a câmera. Uma inferência nativa já em execução pode precisar terminar antes de o processo sair.

```bash
# Observar por 12 segundos, usando outra câmera
python -m nora --camera --camera-id 1 --segundos 12

# Sem janela de vídeo; mensagens continuam no terminal
python -m nora --camera --sem-preview
```

`--segundos` aceita valores de 3 a 60. O tempo é uma janela de coleta, não um prazo rígido: uma inferência em andamento pode ultrapassá-lo. Se o computador produzir menos de 3 amostras nesse período, aumente o tempo. A imagem continua sendo capturada enquanto o único trabalhador executa Mirage ou Needle, sem acumular fila de quadros antigos.

Mirage e Needle são carregados localmente, com download no primeiro uso. Os quadros ficam na memória e não são gravados nem enviados para a Wikipédia; apenas o termo da consulta é enviado. Não há síntese de voz.

O Mirage documenta inglês e outros idiomas, mas não português; a extração usa inglês. A ferramenta procura na Wikipédia em português e, se não obtiver fonte, tenta a edição em inglês, cuja resposta pode vir em inglês. Não há tradução automática. Resultados de pesquisa podem ser ambíguos: a Wikipédia explica o artigo encontrado e **não valida a identificação da câmera**. Este protótipo pode reconhecer uma categoria genérica em vez de marca, modelo ou espécie.

A janela requer uma sessão gráfica e `opencv-python` (não a edição headless). Se a câmera não abrir, feche outros programas que a utilizem, confira as permissões do sistema ou tente `--camera-id 1`. Sem câmera ou modelos disponíveis, o programa informa o erro; não usa reconhecimento simulado como substituto.

Validação desta versão: testes automatizados com webcam, Mirage, Needle e rede simulados, incluindo observação, consenso, pesquisa, bloqueio de chamadas divergentes e liberação da câmera. A captura física e a qualidade da inferência real precisam ser homologadas no computador de destino.
