"""
wevity 공모전 크롤러
- cloudscraper 로 Cloudflare 우회
- 웹/모바일/IT(cidx=20), 게임/소프트웨어(cidx=21) 카테고리 크롤링
- 현재 모집중(D-) 공모전만 추려 data.json 생성
GitHub Actions 에서 주기적으로 실행됨.
"""
import re
import os
import json
import sys
from datetime import datetime, timezone, timedelta

import cloudscraper
import requests
from bs4 import BeautifulSoup

BASE = "https://www.wevity.com"
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "").strip()

# 크롤링할 카테고리 (cidx: 표시이름)
CATEGORIES = {
    20: "웹/모바일/IT",
    21: "게임/소프트웨어",
}
PAGES_PER_CAT = 3          # 카테고리별로 앞에서 몇 페이지까지 볼지
KST = timezone(timedelta(hours=9))

DDAY_RE = re.compile(r"D\s*([-+])\s*(\d+)")
IX_RE = re.compile(r"ix=(\d+)")

scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)


def fetch(cidx: int, gp: int) -> str:
    url = f"{BASE}/index.php?c=find&s=1&gub=1&cidx={cidx}&gp={gp}"
    res = scraper.get(url, timeout=20)
    res.raise_for_status()
    res.encoding = res.apparent_encoding or "utf-8"
    return res.text


def parse(html: str, category: str) -> list[dict]:
    """리스트 페이지에서 공모전 항목들을 추출한다."""
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for li in soup.find_all("li"):
        # 제목 링크: gbn=view + ix 가 있고 텍스트가 있는 a 태그
        anchor = None
        for a in li.find_all("a", href=True):
            href = a["href"]
            if "gbn=view" in href and "ix=" in href and a.get_text(strip=True):
                anchor = a
                break
        if anchor is None:
            continue

        title = anchor.get_text(strip=True)
        href = anchor["href"]
        m = IX_RE.search(href)
        if not m:
            continue
        ix = m.group(1)
        link = href if href.startswith("http") else f"{BASE}/{href.lstrip('/')}"

        # D-day 추출
        text = li.get_text(" ", strip=True)
        dm = DDAY_RE.search(text)
        if not dm:
            continue
        sign, num = dm.group(1), int(dm.group(2))
        dday = f"D{sign}{num}"
        is_open = sign == "-"

        items.append({
            "ix": ix,
            "title": title,
            "link": link,
            "dday": dday,
            "days_left": num if is_open else -num,
            "is_open": is_open,
            "category": category,
        })
    return items


def crawl() -> list[dict]:
    by_ix: dict[str, dict] = {}
    for cidx, name in CATEGORIES.items():
        for gp in range(1, PAGES_PER_CAT + 1):
            try:
                html = fetch(cidx, gp)
            except Exception as e:
                print(f"  [경고] cidx={cidx} gp={gp} 요청 실패: {e}", file=sys.stderr)
                continue
            for item in parse(html, name):
                # 이미 있으면 카테고리만 합쳐서 중복 제거
                if item["ix"] in by_ix:
                    prev = by_ix[item["ix"]]
                    if item["category"] not in prev["category"]:
                        prev["category"] += ", " + item["category"]
                else:
                    by_ix[item["ix"]] = item
    return list(by_ix.values())


def load_previous():
    """기존 data.json 을 읽어 (이미 알던 ix 집합, 초기데이터 여부) 반환."""
    try:
        with open("data.json", encoding="utf-8") as f:
            prev = json.load(f)
        known = {c["ix"] for c in prev.get("contests", [])}
        is_seed = "초기" in prev.get("updated", "")
        return known, is_seed
    except (FileNotFoundError, json.JSONDecodeError):
        return set(), True   # 파일 없으면 첫 실행 = 시드 취급


def notify_discord(new_items):
    """새 공모전을 디스코드 웹훅으로 전송 (임베드, 한 번에 최대 10개씩)."""
    if not DISCORD_WEBHOOK:
        print("  [알림] DISCORD_WEBHOOK 미설정 - 알림 건너뜀")
        return
    if not new_items:
        return

    def color(days):
        return 0xFF5B6E if days <= 3 else (0xFFB14E if days <= 14 else 0x3ECF8E)

    for i in range(0, len(new_items), 10):
        chunk = new_items[i:i + 10]
        embeds = [{
            "title": c["title"][:240],
            "url": c["link"],
            "description": f'{c["category"]} · {c["dday"]}',
            "color": color(c["days_left"]),
        } for c in chunk]
        payload = {"content": f"🆕 새 공모전 {len(new_items)}건!", "embeds": embeds}
        try:
            r = requests.post(DISCORD_WEBHOOK, json=payload, timeout=15)
            r.raise_for_status()
        except Exception as e:
            print(f"  [경고] 디스코드 전송 실패: {e}", file=sys.stderr)
            return
    print(f"  디스코드 알림 전송: {len(new_items)}건")


def main():
    known_ix, is_seed = load_previous()

    all_items = crawl()
    # 모집중(D-)만, 마감 임박순 정렬
    open_items = [x for x in all_items if x["is_open"]]
    open_items.sort(key=lambda x: x["days_left"])

    data = {
        "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "count": len(open_items),
        "contests": open_items,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"수집 완료: 전체 {len(all_items)}건 중 모집중 {len(open_items)}건")
    if not open_items:
        print("  [주의] 모집중 항목 0건 - 사이트 구조 변경 또는 차단 가능성", file=sys.stderr)
        return

    # 새로 뜬 공모전 알림 (첫 실행/시드 데이터일 때는 알림 폭탄 방지로 건너뜀)
    new_items = [c for c in open_items if c["ix"] not in known_ix]
    if is_seed:
        print(f"  시드 실행 - {len(new_items)}건은 알림 없이 등록만 함")
    else:
        notify_discord(new_items)


if __name__ == "__main__":
    main()
