# 🏆 공모전 트래커 (wevity)

위비티(wevity)의 IT/개발 공모전을 주기적으로 크롤링해서 GitHub Pages에 링크로 보여주는 프로젝트.

- `crawler.py` : cloudscraper + BeautifulSoup 으로 크롤링 → `data.json` 생성
- `index.html` : `data.json` 을 읽어 카드/링크로 표시 (검색·분야 필터·마감임박순)
- `.github/workflows/crawl.yml` : 6시간마다 자동 크롤링 후 커밋

## 설정 방법

1. 새 GitHub 레포 만들고 이 파일들 전부 push
2. **Settings → Pages → Source: "Deploy from a branch" → Branch: `main` / `(root)`** 선택
3. **Settings → Actions → General → Workflow permissions → "Read and write permissions"** 체크
4. **Actions** 탭에서 `crawl-contests` 워크플로우 → `Run workflow` 로 한 번 수동 실행
5. `https://<아이디>.github.io/<레포명>/` 접속

이후 6시간마다 자동으로 `data.json` 이 갱신됨.

## 디스코드 알림 (새 공모전 뜰 때)

1. 디스코드 채널 → **설정(톱니) → 연동 → 웹훅 → 새 웹훅** → URL 복사
2. 레포 **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `DISCORD_WEBHOOK`
   - Value: 복사한 웹훅 URL
3. 끝. 다음 크롤링부터 이전에 없던 새 공모전을 디스코드로 쏨.

> 첫 실행(또는 초기 데이터 상태)에서는 알림 폭탄을 막으려고 **알림 없이 등록만** 함.
> 시크릿을 안 넣으면 알림은 그냥 건너뛰고 페이지 갱신만 정상 동작.

## 로컬 테스트

```bash
pip install -r requirements.txt
python crawler.py          # data.json 생성
python -m http.server 8000 # http://localhost:8000 접속
```

## 커스터마이징

- 카테고리 추가/변경: `crawler.py` 의 `CATEGORIES` 딕셔너리 수정 (cidx 값)
  - 22: 과학/공학, 1: 기획/아이디어, 3: 논문/리포트 등
- 페이지 수: `PAGES_PER_CAT`
- 갱신 주기: `crawl.yml` 의 cron 식

## 주의

- 위비티는 Cloudflare 를 쓰므로 `requests` 가 아닌 `cloudscraper` 사용.
- 사이트 HTML 구조가 바뀌면 `parse()` 의 선택자/정규식 조정 필요.
- 크롤링은 과도하게 돌리지 말 것 (6시간 주기면 충분).
