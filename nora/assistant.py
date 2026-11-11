"""Integração real com Cactus/Needle 3 (modelo de chamadas de ferramentas)."""
from __future__ import annotations

import json
import threading

from . import tools


class AssistantService:
    """Instância local single-user. A inferência é serializada pelo lock."""

    def __init__(self) -> None:
        self._agent = None
        self._lock = threading.RLock()

    def _init_agent(self):
        if self._agent is not None:
            return self._agent
        try:
            import cactus
        except ImportError as exc:
            raise RuntimeError("Biblioteca 'cactus-compute' não instalada. Execute python -m pip install -r requirements.txt.") from exc

        @cactus.tool
        def buscar_wikipedia(assunto: str) -> dict:
            """Pesquisar, explicar e consultar um tema, pessoa, animal ou lugar na Wikipédia.

            Args:
                assunto: termo pesquisado, copiado do pedido do usuário
            """
            return tools.wikipedia(assunto)

        @cactus.tool
        def consultar_clima(cidade: str) -> dict:
            """Consultar o clima, tempo, temperatura e umidade atual de uma cidade.

            Args:
                cidade: nome da cidade informado pelo usuário
            """
            return tools.clima(cidade)

        @cactus.tool
        def anotar(texto: str) -> dict:
            """Salvar, guardar, registrar ou lembrar uma anotação dita pelo usuário.

            Args:
                texto: texto da anotação que deve ser guardada
            """
            return tools.salvar_nota(texto)

        @cactus.tool
        def ver_anotacoes() -> dict:
            """Ler, mostrar ou listar as notas e anotações anteriormente salvas."""
            return tools.listar_notas()

        # O primeiro carregamento baixa o runtime e os pesos do Needle 3.
        # Nenhuma chamada de API de LLM é feita na inferência.
        self._agent = cactus.Cactus(
            tools=[buscar_wikipedia, consultar_clima, anotar, ver_anotacoes],
            system="locale: pt-BR; device: computador; assistant: NORA; network: connected",
            generation=3,
        )
        return self._agent

    def ask(self, message: str) -> dict:
        clean = message.strip()
        if not clean:
            return {"reply": "Escreva ou fale uma pergunta.", "sources": [], "tools_used": []}
        if len(clean) > 700:
            return {"reply": "Envie uma mensagem de até 700 caracteres.", "sources": [], "tools_used": []}
        with self._lock:
            agent = self._init_agent()
            # Não aceitamos execução de chamadas externas arbitrárias: apenas as quatro funções definidas acima.
            result = agent.run(clean, max_steps=5, max_new_tokens=256, strict=True)

        executed = result.get("results", []) if isinstance(result, dict) else []
        if isinstance(executed, dict):
            executed = [executed]
        messages: list[str] = []
        sources: list[str] = []
        kinds: list[str] = []
        for item in executed:
            if isinstance(item, str):
                try:
                    item = json.loads(item)
                except json.JSONDecodeError:
                    continue
            # Algumas versões retornam {result: {...}} no envelope.
            if isinstance(item, dict) and isinstance(item.get("result"), dict):
                item = item["result"]
            if not isinstance(item, dict):
                continue
            if item.get("error") and not item.get("message"):
                messages.append("Não consegui executar uma das ações solicitadas.")
                continue
            if item.get("message"):
                messages.append(str(item["message"]))
                if item.get("kind"):
                    kinds.append(str(item["kind"]))
            url = item.get("source")
            if isinstance(url, str) and url.startswith("https://") and url not in sources:
                sources.append(url)
        if not messages:
            messages = ["Ainda não tenho uma ferramenta para esse pedido. Posso consultar a Wikipédia, verificar o clima, gerenciar anotações. Tente formular o pedido com um assunto, cidade ou operação específica."]
        return {"reply": "\n\n".join(messages), "sources": sources, "tools_used": kinds}
