"""Ferramentas determinísticas e verificáveis que o Needle 3 pode acionar.

A IA escolhe ferramentas e extrai argumentos; estas funções buscam os dados
reais e produzem a resposta. Nenhum texto factual é inventado pelo modelo.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

NOTES_FILE = Path(os.environ.get("NORA_NOTES_FILE", str(Path.home() / ".nora" / "notes.json")))
NOTES_LOCK = threading.Lock()
USER_AGENT = "NORA-Needle3/1.0 (educational assistant; Python urllib)"


def _get_json(url: str, params: dict) -> dict:
    full_url = f"{url}?{urlencode(params)}"
    req = Request(full_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=12) as response:
        return json.load(response)


def _error(kind: str, message: str) -> dict:
    return {"kind": kind, "message": message}


def wikipedia(assunto: str, language: str = "pt") -> dict:
    """Pesquisa um assunto na Wikipédia em português e traz um resumo com link."""
    assunto = assunto.strip()[:120]
    if not assunto:
        return _error("wikipedia", "Diga o assunto que deseja pesquisar na Wikipédia.")
    if language not in {"pt", "en"}:
        raise ValueError("Idioma da Wikipédia inválido")
    endpoint = f"https://{language}.wikipedia.org/w/api.php"
    try:
        found = _get_json(endpoint, {
            "action": "query", "list": "search", "srsearch": assunto,
            "srlimit": 1, "format": "json", "utf8": 1,
        })
        entries = found.get("query", {}).get("search", [])
        if not entries:
            return _error("wikipedia", f"Não encontrei um artigo sobre “{assunto}” na Wikipédia.")
        title = entries[0]["title"]
        data = _get_json(endpoint, {
            "action": "query", "prop": "extracts", "titles": title,
            "redirects": 1, "exintro": 1, "explaintext": 1,
            "exsentences": 5, "format": "json", "formatversion": 2,
        })
        pages = data.get("query", {}).get("pages", [])
        page = pages[0] if pages else {}
        article_title = page.get("title", title)
        extract = re.sub(r"\s+", " ", page.get("extract", "")).strip()
        link = f"https://{language}.wikipedia.org/wiki/" + quote(article_title.replace(" ", "_"))
        if not extract:
            return {"kind": "wikipedia", "message": f"Encontrei o artigo “{article_title}”, mas não consegui extrair seu resumo. Abra a fonte para ler.", "source": link}
        if len(extract) > 950:
            extract = extract[:947].rsplit(" ", 1)[0] + "…"
        return {"kind": "wikipedia", "message": f"📖 {article_title}\n\n{extract}", "source": link}
    except (URLError, HTTPError, TimeoutError, ValueError, KeyError, IndexError):
        return _error("wikipedia", "Não consegui consultar a Wikipédia agora. Verifique a conexão e tente novamente.")


WEATHER_CODES = {
    0: "céu limpo", 1: "predominantemente limpo", 2: "parcialmente nublado",
    3: "nublado", 45: "nevoeiro", 48: "nevoeiro com geada",
    51: "garoa leve", 53: "garoa moderada", 55: "garoa forte",
    61: "chuva fraca", 63: "chuva moderada", 65: "chuva forte",
    71: "neve fraca", 73: "neve moderada", 75: "neve intensa",
    80: "pancadas de chuva leves", 81: "pancadas de chuva moderadas",
    82: "pancadas de chuva fortes", 95: "trovoadas",
    96: "trovoadas com granizo", 99: "trovoadas com granizo forte",
}


def clima(cidade: str) -> dict:
    """Consulta a temperatura e o tempo atual de uma cidade via Open-Meteo."""
    cidade = cidade.strip()[:100]
    if not cidade:
        return _error("clima", "Informe uma cidade para consultar a previsão do tempo.")
    try:
        geo = _get_json("https://geocoding-api.open-meteo.com/v1/search", {
            "name": cidade, "count": 1, "language": "pt", "format": "json",
        })
        places = geo.get("results", [])
        if not places:
            return _error("clima", f"Não encontrei a cidade “{cidade}”. Tente informar também o estado.")
        place = places[0]
        forecast = _get_json("https://api.open-meteo.com/v1/forecast", {
            "latitude": place["latitude"], "longitude": place["longitude"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
            "timezone": "auto", "forecast_days": 1,
        })
        current = forecast["current"]
        label = ", ".join(filter(None, [place.get("name"), place.get("admin1"), place.get("country")]))
        description = WEATHER_CODES.get(current.get("weather_code"), "condições variáveis")
        return {
            "kind": "clima",
            "message": (
                f"🌤️ Tempo em {label}\n\n"
                f"{current['temperature_2m']} °C, {description}. "
                f"Sensação térmica de {current['apparent_temperature']} °C, "
                f"umidade de {current['relative_humidity_2m']}% "
                f"e vento a {current['wind_speed_10m']} km/h."
            ),
            "source": "https://open-meteo.com/",
        }
    except (URLError, HTTPError, TimeoutError, ValueError, KeyError, IndexError, TypeError):
        return _error("clima", "Não consegui consultar o clima agora. Verifique sua conexão e tente novamente.")


def _read_notes() -> list[dict]:
    if not NOTES_FILE.exists():
        return []
    try:
        data = json.loads(NOTES_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list) or any(not isinstance(item, dict) for item in data):
            raise ValueError("Formato do arquivo de notas inválido.")
        return data
    except json.JSONDecodeError as exc:
        raise ValueError("Arquivo de notas inválido; restaure uma cópia antes de salvar novas notas.") from exc


def salvar_nota(texto: str) -> dict:
    """Guarda uma anotação local em JSON, sem enviar o conteúdo a serviços externos."""
    texto = texto.strip()[:500]
    if not texto:
        return _error("notas", "Qual anotação você gostaria de salvar?")
    with NOTES_LOCK:
        notes = _read_notes()
        entry = {"texto": texto, "data": datetime.now().astimezone().isoformat(timespec="minutes")}
        notes.append(entry)
        NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=NOTES_FILE.parent, delete=False, suffix=".tmp") as f:
                temp_file = Path(f.name)
                json.dump(notes[-100:], f, ensure_ascii=False, indent=2)
            os.replace(temp_file, NOTES_FILE)
        finally:
            if temp_file and temp_file.exists():
                temp_file.unlink()
    return {"kind": "notas", "message": f"📝 Anotação salva: {texto}"}


def listar_notas() -> dict:
    """Lista as últimas anotações salvas localmente pelo assistente."""
    with NOTES_LOCK:
        notes = _read_notes()
    if not notes:
        return _error("notas", "Você ainda não tem anotações salvas. Peça: anote comprar café.")
    lines = [f"{n}. {item.get('texto', '')}" for n, item in enumerate(notes[-10:], 1)]
    return {"kind": "notas", "message": "🗒️ Suas últimas anotações:\n\n" + "\n".join(lines)}
