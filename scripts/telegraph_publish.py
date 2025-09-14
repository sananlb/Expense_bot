#!/usr/bin/env python3
"""
Публикация документов (Политика/Оферта) в Telegraph, как в Nutrition_bot.

Использование:
  export TELEGRAPH_ACCESS_TOKEN=...  # получить через https://telegra.ph/api
  python scripts/telegraph_publish.py --type privacy --title "Coins — Политика конфиденциальности" --source docs/PRIVACY_POLICY_EXPENSEBOT.txt
  python scripts/telegraph_publish.py --type offer   --title "Coins — Публичная оферта"            --source docs/PUBLIC_OFFER_EXPENSEBOT.txt

На выходе скрипт печатает URL страницы. Этот URL можно записать в .env:
  TELEGRAPH_PRIVACY_URL=...
  TELEGRAPH_OFFER_URL=...

Примечание: Для простоты конвертируем текст в минимальный HTML (абзацы/строки).
"""
import argparse
import html
import os
import sys
import requests

API_BASE = "https://api.telegra.ph"


def to_simple_html(text: str) -> str:
    # Экранируем HTML и превращаем двойные переводы строк в параграфы
    escaped = html.escape(text)
    paragraphs = [p.strip() for p in escaped.split("\n\n") if p.strip()]
    html_parts = []
    for p in paragraphs:
        # Поддержка маркированных списков из строк, начинающихся с "- "
        lines = p.splitlines()
        if all(line.startswith("- ") for line in lines):
            html_parts.append("<ul>" + "".join(f"<li>{html.escape(line[2:].strip())}</li>" for line in lines) + "</ul>")
        else:
            # Переводы строк внутри параграфа превращаем в <br/>
            html_parts.append("<p>" + "<br/>".join(lines) + "</p>")
    return "\n".join(html_parts)


def create_page(access_token: str, title: str, content_html: str) -> str:
    r = requests.post(
        f"{API_BASE}/createPage",
        data={
            "access_token": access_token,
            "title": title,
            "content": content_html,
            "author_name": "Coins Bot",
            "return_content": False,
        },
    )
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegraph error: {data}")
    return data["result"]["url"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["privacy", "offer"], required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--source", required=True, help="Путь к файлу .txt/.md с текстом")
    args = parser.parse_args()

    token = os.getenv("TELEGRAPH_ACCESS_TOKEN")
    if not token:
        print("ERROR: TELEGRAPH_ACCESS_TOKEN is not set", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.source):
        print(f"ERROR: source file not found: {args.source}", file=sys.stderr)
        sys.exit(1)

    with open(args.source, "r", encoding="utf-8") as f:
        raw = f.read()

    content_html = to_simple_html(raw)
    url = create_page(token, args.title, content_html)
    print(url)

    # Подсказка: можно автоматически записать в .env
    env_key = "TELEGRAPH_PRIVACY_URL" if args.type == "privacy" else "TELEGRAPH_OFFER_URL"
    print(f"\nSet in .env: {env_key}={url}")


if __name__ == "__main__":
    main()

