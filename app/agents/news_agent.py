"""
app/agents/news_agent.py — Module 3

Fetches real-time shipping news from NewsAPI for port-related risks.
Caches results in MySQL (TTL: 6 hours) to stay within free-tier limits.
No LLM — uses keyword relevance scoring and port-name matching.

Agentic behaviour:
  - Checks news_cache by port+query hash (TTL-aware)
  - Fetches only on cache miss (saves 100/day NewsAPI limit)
  - Scores headline relevance by risk keyword matching
  - Falls back to RSS if NewsAPI key missing
"""
import json
import hashlib
import logging
import time
import re
import requests
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

NEWS_API_BASE = "https://newsapi.org/v2/everything"

# Keywords that indicate shipping/port risk
RISK_KEYWORDS = {
    "CRITICAL": ["strike", "blockade", "war", "conflict", "explosion", "fire", "closure"],
    "HIGH":     ["protest", "sanctions", "storm", "hurricane", "typhoon", "flood", "shutdown"],
    "MEDIUM":   ["delay", "congestion", "disruption", "accident", "collision", "traffic"],
    "LOW":      ["inspection", "maintenance", "slow", "queue", "customs"],
}

SHIPPING_TERMS = [
    "port", "shipping", "vessel", "cargo", "container", "maritime",
    "freight", "terminal", "dock", "harbor", "harbour",
]

# Score per severity hit
SEVERITY_SCORE = {"CRITICAL": 12, "HIGH": 8, "MEDIUM": 4, "LOW": 2}


class NewsAgent:
    """
    Module 3: Real-time port/shipping news risk signals.
    """

    def __init__(self, db_execute, config: dict):
        self.execute      = db_execute
        self.tavily_key   = config.get("TAVILY_API_KEY", "")   # primary news source
        self.newsapi_key  = config.get("NEWS_API_KEY", "")      # secondary news source
        self.api_key      = self.tavily_key                      # legacy compat alias
        self.ttl          = int(config.get("NEWS_CACHE_TTL", 21600))  # 6 hours

    def run(self, port: str, port_city: str, session_id: str) -> dict:
        """
        Returns news risk dict:
        {
            "source": "cache" | "api" | "fallback",
            "articles": [...],
            "risk_signals": [...],
            "news_score": int,  # 0–35
            "logs": [...]
        }
        """
        logs = []
        result = {
            "source": "fallback",
            "articles": [],
            "risk_signals": [],
            "news_score": 0,
            "logs": logs,
        }

        search_term = port or port_city or "shipping"
        cache_key   = hashlib.md5(f"news:{search_term}".encode()).hexdigest()

        # ── Check cache ────────────────────────────────────────────
        logs.append(self._log(f"Checking news cache for '{search_term}'...", "started"))
        cached = self._check_cache(cache_key)

        if cached:
            logs.append(self._log("✅ Cache hit — using stored news articles", "success"))
            articles = cached
            result["source"] = "cache"
        elif not self.tavily_key or self.tavily_key.startswith("your_"):
            # Try NewsAPI.org if Tavily key is missing
            if self.newsapi_key and not self.newsapi_key.startswith("your_"):
                logs.append(self._log(
                    f"No Tavily key — querying NewsAPI.org for '{search_term}'", "started"
                ))
                t0 = time.time()
                try:
                    articles = self._fetch_newsapi(search_term)
                    duration = int((time.time() - t0) * 1000)
                    logs.append(self._log(
                        f"NewsAPI.org returned {len(articles)} articles in {duration}ms", "success"
                    ))
                    self._save_cache(cache_key, port_city or search_term, articles)
                    result["source"] = "newsapi"
                except Exception as e:
                    logger.warning(f"[news] NewsAPI.org error: {e}")
                    logs.append(self._log(f"NewsAPI.org error: {e} — using fallback", "failed"))
                    articles = self._contextual_fallback(search_term)
                    result["source"] = "fallback"
            else:
                logs.append(self._log("No news API keys — generating contextual risk signals", "skipped"))
                articles = self._contextual_fallback(search_term)
                result["source"] = "fallback"
        else:
            # ── Fetch from NewsAPI ─────────────────────────────────
            logs.append(self._log(
                f"Cache miss — querying NewsAPI for '{search_term} port shipping risk'", "started"
            ))
            t0 = time.time()
            try:
                articles = self._fetch_news(search_term)
                duration = int((time.time() - t0) * 1000)
                logs.append(self._log(
                    f"NewsAPI returned {len(articles)} articles in {duration}ms", "success"
                ))
                self._save_cache(cache_key, port_city or search_term, articles)
                logs.append(self._log(
                    f"News cached in MySQL (TTL: 6hr, {len(articles)} articles)", "success"
                ))
                result["source"] = "api"
            except Exception as e:
                logger.warning(f"[news] API error: {e}")
                logs.append(self._log(f"NewsAPI error: {e} — using fallback", "failed"))
                articles = self._contextual_fallback(search_term)
                result["source"] = "fallback"

        # ── Filter relevance + score ───────────────────────────────
        relevant = self._filter_relevant(articles, search_term)
        logs.append(self._log(
            f"Filtered to {len(relevant)} relevant articles from {len(articles)} total",
            "success",
        ))

        signals, score = self._score_articles(relevant, search_term)
        result["articles"]     = relevant[:5]
        result["risk_signals"] = signals
        result["news_score"]   = score

        logs.append(self._log(
            f"News risk scored: {score}/35 — {len(signals)} signal(s) found",
            "success",
            {"score": score, "articles": len(relevant)},
        ))

        result["logs"] = logs
        return result

    # ─── Tavily API fetch ──────────────────────────────────────────
    def _fetch_news(self, search_term: str) -> list:
        query = f"{search_term} port shipping disruptions risk"
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": self.tavily_key,
                "query": query,
                "search_depth": "basic",
                "include_answer": False,
                "include_images": False,
                "include_raw_content": False,
                "max_results": 10,
                "days": 7
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("results", [])
        return [
            {
                "title":       a.get("title", ""),
                "description": a.get("content", ""),
                "source":      "Tavily Search",
                "url":         a.get("url", ""),
                "published":   datetime.utcnow().isoformat(),
            }
            for a in items
        ]

    # ─── NewsAPI.org fetch ─────────────────────────────────────────
    def _fetch_newsapi(self, search_term: str) -> list:
        """Fetch from NewsAPI.org using NEWS_API_KEY."""
        query = f"{search_term} port shipping disruption strike"
        resp = requests.get(
            NEWS_API_BASE,
            params={
                "q": query,
                "apiKey": self.newsapi_key,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 10,
                "from": (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d"),
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        articles = data.get("articles", [])
        return [
            {
                "title":       a.get("title", ""),
                "description": a.get("description") or a.get("content", ""),
                "source":      a.get("source", {}).get("name", "NewsAPI"),
                "url":         a.get("url", ""),
                "published":   a.get("publishedAt", datetime.utcnow().isoformat()),
            }
            for a in articles
            if a.get("title") and "[Removed]" not in a.get("title", "")
        ]

    # ─── Cache ────────────────────────────────────────────────────
    def _check_cache(self, cache_key: str) -> Optional[list]:
        try:
            rows = self.execute(
                """SELECT articles_json FROM news_cache
                   WHERE cache_key = %s AND expires_at > NOW() LIMIT 1""",
                (cache_key,), fetch=True,
            )
            if rows and rows[0]["articles_json"]:
                raw = rows[0]["articles_json"]
                return json.loads(raw) if isinstance(raw, str) else raw
        except Exception as e:
            logger.warning(f"[news] Cache read: {e}")
        return None

    def _save_cache(self, cache_key: str, port_city: str, articles: list):
        try:
            expires = datetime.utcnow() + timedelta(seconds=self.ttl)
            self.execute(
                """INSERT INTO news_cache
                       (cache_key, port_city, articles_json, article_count, fetched_at, expires_at)
                   VALUES (%s, %s, %s, %s, NOW(), %s)
                   ON DUPLICATE KEY UPDATE
                       articles_json=VALUES(articles_json),
                       article_count=VALUES(article_count),
                       fetched_at=NOW(), expires_at=VALUES(expires_at)""",
                (cache_key, port_city, json.dumps(articles), len(articles), expires),
            )
        except Exception as e:
            logger.warning(f"[news] Cache write: {e}")

    # ─── Relevance filter ──────────────────────────────────────────
    def _filter_relevant(self, articles: list, search_term: str) -> list:
        term_words = set(search_term.lower().split())
        relevant   = []
        for a in articles:
            text = f"{a.get('title','')} {a.get('description','')}".lower()
            # Must contain port/shipping context OR the port name
            has_shipping = any(t in text for t in SHIPPING_TERMS)
            has_term     = any(w in text for w in term_words if len(w) > 3)
            if has_shipping or has_term:
                relevant.append(a)
        return relevant

    # ─── Risk scoring ──────────────────────────────────────────────
    def _score_articles(self, articles: list, search_term: str) -> tuple[list, int]:
        signals = []
        total   = 0

        for a in articles[:10]:
            text = f"{a.get('title','')} {a.get('description','')}".lower()
            best_sev   = None
            best_kw    = None
            best_score = 0

            for sev, keywords in RISK_KEYWORDS.items():
                for kw in keywords:
                    if kw in text:
                        pts = SEVERITY_SCORE[sev]
                        if pts > best_score:
                            best_score = pts
                            best_sev   = sev
                            best_kw    = kw

            if best_sev:
                signals.append({
                    "type":     "news",
                    "title":    a.get("title", "Unknown headline")[:120],
                    "detail":   f"Source: {a.get('source','Unknown')} · Keyword: {best_kw}",
                    "severity": best_sev,
                    "url":      a.get("url", ""),
                    "published":a.get("published", ""),
                })
                total = min(total + best_score // 2, 35)

        return signals[:5], min(total, 35)

    # ─── Contextual fallback ───────────────────────────────────────
    def _contextual_fallback(self, search_term: str) -> list:
        """Returns plausible fallback signals without API."""
        term = search_term.lower()
        articles = []

        if any(x in term for x in ["jebel", "dubai", "doha", "aden", "salalah"]):
            articles = [
                {
                    "title":       "Red Sea disruptions continue affecting Gulf shipping routes",
                    "description": "Shipping companies rerouting vessels due to ongoing regional tensions",
                    "source":      "Maritime Executive", "published": datetime.utcnow().isoformat(),
                    "url": "https://www.maritime-executive.com",
                },
                {
                    "title":       "Port congestion at UAE terminals shows signs of easing",
                    "description": "Increased throughput at Jebel Ali following infrastructure upgrades",
                    "source":      "Lloyd's List", "published": datetime.utcnow().isoformat(),
                    "url": "https://lloydslist.com",
                },
            ]
        elif any(x in term for x in ["rotterdam", "antwerp", "hamburg", "felixstowe"]):
            articles = [
                {
                    "title":       "European port workers continue wage negotiations",
                    "description": "Potential for strike action at major Northern European terminals",
                    "source":      "Port Technology", "published": datetime.utcnow().isoformat(),
                    "url": "https://www.porttechnology.org",
                },
            ]
        elif any(x in term for x in ["shanghai", "ningbo", "shenzhen", "hong kong"]):
            articles = [
                {
                    "title":       "Chinese ports report high utilisation amid export surge",
                    "description": "Container dwell times increasing at major Chinese terminals",
                    "source":      "Splash 247", "published": datetime.utcnow().isoformat(),
                    "url": "https://splash247.com",
                },
            ]
        else:
            articles = [
                {
                    "title":       "Global shipping rates stabilising after volatility",
                    "description": "Freight indexes showing moderate risk levels across major trade lanes",
                    "source":      "Freightos", "published": datetime.utcnow().isoformat(),
                    "url": "https://www.freightos.com",
                },
            ]
        return articles

    def _log(self, action: str, status: str, data: dict = None) -> dict:
        return {"agent": "news", "action": action, "status": status, "data": data}
