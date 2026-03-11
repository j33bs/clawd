from __future__ import annotations

import json
import math
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests


UTC = timezone.utc


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except Exception:
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _regime_from_sentiment(sentiment: float) -> str:
    if sentiment >= 0.2:
        return "risk_on"
    if sentiment <= -0.2:
        return "risk_off"
    return "neutral"


def _parse_macro_value(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    upper = text.replace(",", "").replace("\u2212", "-").upper()
    upper = upper.replace("<", "").replace(">", "").replace("≈", "").replace("~", "")
    match = re.search(r"[-+]?\d*\.?\d+", upper)
    if not match:
        return None
    number = float(match.group(0))
    suffix = upper[match.end() :].strip()
    multiplier = 1.0
    if suffix.startswith("K"):
        multiplier = 1_000.0
    elif suffix.startswith("M"):
        multiplier = 1_000_000.0
    elif suffix.startswith("B"):
        multiplier = 1_000_000_000.0
    elif suffix.startswith("T"):
        multiplier = 1_000_000_000_000.0
    return number * multiplier


def _surprise_score(actual: Any, forecast: Any, previous: Any) -> float | None:
    actual_num = _parse_macro_value(actual)
    baseline_num = _parse_macro_value(forecast)
    if baseline_num is None:
        baseline_num = _parse_macro_value(previous)
    if actual_num is None or baseline_num is None:
        return None
    scale = max(abs(baseline_num), 1.0)
    return clamp((actual_num - baseline_num) / scale, -5.0, 5.0)


@dataclass
class SourceData:
    name: str
    optional: bool
    weight_hint: float
    status: str
    fetched_at: str
    url: str
    raw_content: bytes
    raw_extension: str
    transport: dict[str, Any]
    metrics: dict[str, Any]
    heuristic: dict[str, Any]
    summary: str
    error: str | None = None


class MarketSource:
    def __init__(self, *, name: str, config: dict[str, Any]):
        self.name = name
        self.config = config
        self.optional = bool(config.get("optional", False))
        self.weight_hint = float(config.get("weight_hint", 1.0))
        self.timeout_seconds = int(config.get("timeout_seconds", 20))

    def _error(self, reason: str, *, url: str, fetched_at: str) -> SourceData:
        status = "optional_offline" if self.optional else "error"
        return SourceData(
            name=self.name,
            optional=self.optional,
            weight_hint=self.weight_hint,
            status=status,
            fetched_at=fetched_at,
            url=url,
            raw_content=b"",
            raw_extension="txt",
            transport={"url": url, "http_status": None},
            metrics={"reason": reason},
            heuristic={
                "sentiment": 0.0,
                "confidence": 0.0,
                "risk_on": 0.0,
                "risk_off": 0.0,
                "regime": "neutral",
                "drivers": [],
            },
            summary=reason,
            error=reason,
        )


class ForexFactorySource(MarketSource):
    def fetch(self, session: requests.Session) -> SourceData:
        fetched_at = utc_now_iso()
        url = str(self.config.get("url") or "")
        if not url:
            return self._error("missing_url", url="", fetched_at=fetched_at)
        try:
            resp = session.get(url, timeout=self.timeout_seconds)
            resp.raise_for_status()
        except Exception as exc:
            return self._error(f"fetch_failed:{exc}", url=url, fetched_at=fetched_at)
        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as exc:
            return self._error(f"xml_parse_failed:{exc}", url=url, fetched_at=fetched_at)

        today = datetime.now(UTC).date()
        horizon = today + timedelta(days=2)
        impact_counts = {"High": 0, "Medium": 0, "Low": 0, "Holiday": 0, "Non-Economic": 0}
        next_two_days: list[dict[str, Any]] = []
        countries: dict[str, int] = {}
        surprise_ready = 0
        surprise_events: list[dict[str, Any]] = []
        surprise_events_next_2d: list[dict[str, Any]] = []

        for node in root.findall(".//event"):
            title = (node.findtext("title") or "").strip()
            country = (node.findtext("country") or "").strip()
            date_text = (node.findtext("date") or "").strip()
            time_text = (node.findtext("time") or "").strip()
            impact = (node.findtext("impact") or "Low").strip() or "Low"
            forecast = (node.findtext("forecast") or "").strip()
            previous = (node.findtext("previous") or "").strip()
            actual = (node.findtext("actual") or "").strip()
            try:
                event_date = datetime.strptime(date_text, "%m-%d-%Y").date()
            except ValueError:
                continue
            impact_counts[impact] = impact_counts.get(impact, 0) + 1
            countries[country] = countries.get(country, 0) + 1
            if actual and forecast:
                surprise_ready += 1
            surprise = _surprise_score(actual, forecast, previous)
            if surprise is not None:
                surprise_row = {
                    "date": event_date.isoformat(),
                    "country": country,
                    "impact": impact,
                    "title": title,
                    "actual": actual,
                    "forecast": forecast,
                    "previous": previous,
                    "surprise_score": round(surprise, 6),
                }
                surprise_events.append(surprise_row)
                if today <= event_date <= horizon:
                    surprise_events_next_2d.append(surprise_row)
            if today <= event_date <= horizon:
                next_two_days.append(
                    {
                        "date": event_date.isoformat(),
                        "time": time_text,
                        "country": country,
                        "impact": impact,
                        "title": title,
                        "forecast": forecast,
                        "previous": previous,
                        "actual": actual,
                    }
                )

        next_two_days.sort(key=lambda item: (item["date"], item["impact"] != "High", item["country"], item["title"]))
        surprise_events.sort(key=lambda item: abs(float(item["surprise_score"])), reverse=True)
        surprise_events_next_2d.sort(key=lambda item: abs(float(item["surprise_score"])), reverse=True)
        top_events = [
            f"{row['date']} {row['country']} {row['impact']} {row['title']}"
            for row in next_two_days[:5]
        ]
        weighted_surprise_sum = 0.0
        weighted_surprise_weight = 0.0
        impact_weight = {"High": 1.0, "Medium": 0.7, "Low": 0.35, "Holiday": 0.15, "Non-Economic": 0.15}
        for row in surprise_events:
            weight = impact_weight.get(row["impact"], 0.35)
            weighted_surprise_sum += float(row["surprise_score"]) * weight
            weighted_surprise_weight += weight
        surprise_balance_week = (weighted_surprise_sum / weighted_surprise_weight) if weighted_surprise_weight else 0.0
        top_surprises = [
            f"{row['date']} {row['country']} {row['title']} {row['actual']} vs {row['forecast'] or row['previous']} ({row['surprise_score']:+.2f})"
            for row in surprise_events[:5]
        ]
        heuristic_confidence = clamp(0.18 + (0.03 * len(next_two_days)) + (0.04 * min(4, surprise_ready)), 0.15, 0.65)
        heuristic = {
            "sentiment": 0.0,
            "confidence": round(heuristic_confidence, 6),
            "risk_on": 0.5,
            "risk_off": 0.5,
            "regime": "neutral",
            "drivers": (top_surprises or top_events)[:3],
        }
        metrics = {
            "events_total": sum(impact_counts.values()),
            "high_impact_next_2d": sum(1 for row in next_two_days if row["impact"] == "High"),
            "medium_impact_next_2d": sum(1 for row in next_two_days if row["impact"] == "Medium"),
            "usd_high_next_2d": sum(1 for row in next_two_days if row["impact"] == "High" and row["country"] == "USD"),
            "surprise_ready_events": surprise_ready,
            "surprise_events_week": len(surprise_events),
            "positive_surprise_events_week": sum(1 for row in surprise_events if float(row["surprise_score"]) > 0),
            "negative_surprise_events_week": sum(1 for row in surprise_events if float(row["surprise_score"]) < 0),
            "surprise_balance_week": round(clamp(surprise_balance_week, -5.0, 5.0), 6),
            "top_surprise_events_week": top_surprises,
            "top_surprise_events_next_2d": [
                f"{row['date']} {row['country']} {row['title']} {row['actual']} vs {row['forecast'] or row['previous']} ({row['surprise_score']:+.2f})"
                for row in surprise_events_next_2d[:5]
            ],
            "impact_counts_week": impact_counts,
            "top_countries_week": sorted(countries.items(), key=lambda item: (-item[1], item[0]))[:5],
            "sample_events": top_events,
        }
        summary = (
            f"Forex Factory weekly feed shows {metrics['high_impact_next_2d']} high-impact and "
            f"{metrics['medium_impact_next_2d']} medium-impact events in the next 2 days; "
            f"{metrics['usd_high_next_2d']} of those high-impact events are USD-related. "
            f"Released surprise balance for the week is {metrics['surprise_balance_week']:+.2f}. "
            f"Top surprises: {'; '.join(top_surprises[:3]) if top_surprises else 'none yet'}."
        )
        return SourceData(
            name=self.name,
            optional=self.optional,
            weight_hint=self.weight_hint,
            status="ok",
            fetched_at=fetched_at,
            url=url,
            raw_content=resp.content,
            raw_extension="xml",
            transport={"url": url, "http_status": resp.status_code},
            metrics=metrics,
            heuristic=heuristic,
            summary=summary,
        )


class CoinGeckoSource(MarketSource):
    def fetch(self, session: requests.Session) -> SourceData:
        fetched_at = utc_now_iso()
        base_url = str(self.config.get("base_url") or "https://api.coingecko.com/api/v3").rstrip("/")
        api_key_env = str(self.config.get("api_key_env") or "COINGECKO_API_KEY")
        api_key = os.environ.get(api_key_env) or os.environ.get("CG_API_KEY")
        vs_currency = str(self.config.get("vs_currency") or "usd")
        per_page = int(self.config.get("markets_limit", 20))
        headers = {"Accept": "application/json"}
        if api_key:
            header_name = "x-cg-pro-api-key" if "pro-api.coingecko.com" in base_url else "x-cg-demo-api-key"
            headers[header_name] = api_key
        try:
            global_resp = session.get(f"{base_url}/global", headers=headers, timeout=self.timeout_seconds)
            global_resp.raise_for_status()
            markets_resp = session.get(
                f"{base_url}/coins/markets",
                params={
                    "vs_currency": vs_currency,
                    "order": "market_cap_desc",
                    "per_page": per_page,
                    "page": 1,
                    "sparkline": "false",
                    "price_change_percentage": "24h,7d",
                },
                headers=headers,
                timeout=self.timeout_seconds,
            )
            markets_resp.raise_for_status()
            trending_resp = session.get(f"{base_url}/search/trending", headers=headers, timeout=self.timeout_seconds)
            trending_resp.raise_for_status()
        except Exception as exc:
            return self._error(f"fetch_failed:{exc}", url=base_url, fetched_at=fetched_at)

        global_data = (global_resp.json() or {}).get("data") or {}
        markets = markets_resp.json() or []
        trending = (trending_resp.json() or {}).get("coins") or []

        positive = 0
        weighted_sum = 0.0
        market_cap_sum = 0.0
        pct_7d_sum = 0.0
        pct_7d_count = 0
        top_movers: list[tuple[str, float]] = []
        for item in markets:
            price_24h = _safe_float(item.get("price_change_percentage_24h_in_currency"))
            price_7d = _safe_float(item.get("price_change_percentage_7d_in_currency"))
            market_cap = max(0.0, _safe_float(item.get("market_cap")))
            name = str(item.get("symbol") or item.get("name") or "").upper()
            if price_24h > 0:
                positive += 1
            weighted_sum += market_cap * price_24h
            market_cap_sum += market_cap
            if price_7d or item.get("price_change_percentage_7d_in_currency") is not None:
                pct_7d_sum += price_7d
                pct_7d_count += 1
            top_movers.append((name, price_24h))

        green_ratio = (positive / len(markets)) if markets else 0.0
        weighted_24h = (weighted_sum / market_cap_sum) if market_cap_sum else 0.0
        avg_7d = (pct_7d_sum / pct_7d_count) if pct_7d_count else 0.0
        market_cap_change = _safe_float(global_data.get("market_cap_change_percentage_24h_usd"))
        market_cap_pct = global_data.get("market_cap_percentage") or {}
        btc_dominance = _safe_float(market_cap_pct.get("btc"))
        eth_dominance = _safe_float(market_cap_pct.get("eth"))
        trending_symbols = []
        for item in trending[:7]:
            coin = item.get("item") or {}
            symbol = str(coin.get("symbol") or "").upper()
            if symbol:
                trending_symbols.append(symbol)
        top_movers.sort(key=lambda item: item[1], reverse=True)

        sentiment = clamp(
            (market_cap_change / 5.0) * 0.45
            + ((green_ratio - 0.5) * 2.0) * 0.35
            + (weighted_24h / 6.0) * 0.20,
            -1.0,
            1.0,
        )
        heuristic = {
            "sentiment": round(sentiment, 6),
            "confidence": round(clamp(0.55 + (abs(sentiment) * 0.18) + (min(len(markets), 20) / 120.0), 0.45, 0.92), 6),
            "risk_on": round(clamp(max(0.0, sentiment), 0.0, 1.0), 6),
            "risk_off": round(clamp(max(0.0, -sentiment), 0.0, 1.0), 6),
            "regime": _regime_from_sentiment(sentiment),
            "drivers": [f"{symbol} {change:+.2f}% 24h" for symbol, change in top_movers[:3]],
        }
        metrics = {
            "market_cap_change_24h_pct": round(market_cap_change, 6),
            "green_ratio_top_n": round(green_ratio, 6),
            "weighted_return_24h_pct_top_n": round(weighted_24h, 6),
            "avg_return_7d_pct_top_n": round(avg_7d, 6),
            "btc_dominance_pct": round(btc_dominance, 6),
            "eth_dominance_pct": round(eth_dominance, 6),
            "trending_symbols": trending_symbols,
            "top_movers_24h": [f"{symbol}:{change:+.2f}" for symbol, change in top_movers[:5]],
        }
        summary = (
            f"CoinGecko top {len(markets)} breadth is {green_ratio:.0%} green with "
            f"{market_cap_change:+.2f}% total market-cap change over 24h and {weighted_24h:+.2f}% "
            f"market-cap-weighted top-{len(markets)} return. BTC dominance is {btc_dominance:.2f}%. "
            f"Trending symbols: {', '.join(trending_symbols) if trending_symbols else 'none'}."
        )
        raw_bundle = json.dumps(
            {
                "global": global_resp.json(),
                "markets": markets,
                "trending": trending_resp.json(),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return SourceData(
            name=self.name,
            optional=self.optional,
            weight_hint=self.weight_hint,
            status="ok",
            fetched_at=fetched_at,
            url=base_url,
            raw_content=raw_bundle,
            raw_extension="json",
            transport={"url": base_url, "http_status": 200},
            metrics=metrics,
            heuristic=heuristic,
            summary=summary,
        )


class CoinMarketCapSource(MarketSource):
    def fetch(self, session: requests.Session) -> SourceData:
        fetched_at = utc_now_iso()
        base_url = str(self.config.get("base_url") or "https://pro-api.coinmarketcap.com").rstrip("/")
        api_key_env = str(self.config.get("api_key_env") or "COINMARKETCAP_API_KEY")
        api_key = os.environ.get(api_key_env) or os.environ.get("CMC_API_KEY")
        if not api_key:
            return self._error(f"missing_api_key_env:{api_key_env}", url=base_url, fetched_at=fetched_at)
        limit = int(self.config.get("limit", 20))
        headers = {"Accept": "application/json", "X-CMC_PRO_API_KEY": api_key}
        try:
            listings_resp = session.get(
                f"{base_url}/v1/cryptocurrency/listings/latest",
                params={"convert": "USD", "limit": limit},
                headers=headers,
                timeout=self.timeout_seconds,
            )
            listings_resp.raise_for_status()
        except Exception as exc:
            return self._error(f"fetch_failed:{exc}", url=base_url, fetched_at=fetched_at)

        listings = (listings_resp.json() or {}).get("data") or []
        positive = 0
        weighted_sum = 0.0
        market_cap_sum = 0.0
        pct_7d_sum = 0.0
        top_movers: list[tuple[str, float]] = []
        for item in listings:
            quote = ((item.get("quote") or {}).get("USD")) or {}
            pct_24h = _safe_float(quote.get("percent_change_24h"))
            pct_7d = _safe_float(quote.get("percent_change_7d"))
            market_cap = max(0.0, _safe_float(quote.get("market_cap")))
            symbol = str(item.get("symbol") or "").upper()
            if pct_24h > 0:
                positive += 1
            weighted_sum += market_cap * pct_24h
            market_cap_sum += market_cap
            pct_7d_sum += pct_7d
            top_movers.append((symbol, pct_24h))

        green_ratio = (positive / len(listings)) if listings else 0.0
        weighted_24h = (weighted_sum / market_cap_sum) if market_cap_sum else 0.0
        avg_7d = (pct_7d_sum / len(listings)) if listings else 0.0
        top_movers.sort(key=lambda item: item[1], reverse=True)
        sentiment = clamp(
            ((green_ratio - 0.5) * 2.0) * 0.55 + (weighted_24h / 6.0) * 0.45,
            -1.0,
            1.0,
        )
        heuristic = {
            "sentiment": round(sentiment, 6),
            "confidence": round(clamp(0.5 + abs(sentiment) * 0.2, 0.45, 0.88), 6),
            "risk_on": round(clamp(max(0.0, sentiment), 0.0, 1.0), 6),
            "risk_off": round(clamp(max(0.0, -sentiment), 0.0, 1.0), 6),
            "regime": _regime_from_sentiment(sentiment),
            "drivers": [f"{symbol} {change:+.2f}% 24h" for symbol, change in top_movers[:3]],
        }
        metrics = {
            "green_ratio_top_n": round(green_ratio, 6),
            "weighted_return_24h_pct_top_n": round(weighted_24h, 6),
            "avg_return_7d_pct_top_n": round(avg_7d, 6),
            "top_movers_24h": [f"{symbol}:{change:+.2f}" for symbol, change in top_movers[:5]],
        }
        summary = (
            f"CoinMarketCap top {len(listings)} breadth is {green_ratio:.0%} green with "
            f"{weighted_24h:+.2f}% market-cap-weighted 24h return and {avg_7d:+.2f}% average 7d return."
        )
        return SourceData(
            name=self.name,
            optional=self.optional,
            weight_hint=self.weight_hint,
            status="ok",
            fetched_at=fetched_at,
            url=base_url,
            raw_content=json.dumps(listings_resp.json(), ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            raw_extension="json",
            transport={"url": base_url, "http_status": listings_resp.status_code},
            metrics=metrics,
            heuristic=heuristic,
            summary=summary,
        )


class FearGreedSource(MarketSource):
    def fetch(self, session: requests.Session) -> SourceData:
        fetched_at = utc_now_iso()
        url = str(self.config.get("url") or "https://api.alternative.me/fng/").rstrip("/")
        try:
            response = session.get(
                url,
                params={"limit": 2, "format": "json"},
                headers={"Accept": "application/json"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except Exception as exc:
            return self._error(f"fetch_failed:{exc}", url=url, fetched_at=fetched_at)

        data = (response.json() or {}).get("data") or []
        latest = data[0] if data else {}
        previous = data[1] if len(data) > 1 else {}
        value = _safe_float(latest.get("value"))
        previous_value = _safe_float(previous.get("value"))
        delta = value - previous_value if previous else 0.0
        sentiment = clamp((value - 50.0) / 40.0, -1.0, 1.0)
        time_until_update = int(_safe_float(latest.get("time_until_update"), 0.0))
        classification = str(latest.get("value_classification") or "unknown").strip() or "unknown"
        previous_classification = str(previous.get("value_classification") or "").strip()
        heuristic = {
            "sentiment": round(sentiment, 6),
            "confidence": round(clamp(0.55 + abs(sentiment) * 0.25, 0.5, 0.9), 6),
            "risk_on": round(clamp(max(0.0, sentiment), 0.0, 1.0), 6),
            "risk_off": round(clamp(max(0.0, -sentiment), 0.0, 1.0), 6),
            "regime": _regime_from_sentiment(sentiment),
            "drivers": [
                f"fear_greed={value:.0f} {classification}",
                f"delta_1d={delta:+.0f}" if previous else "delta_1d=unknown",
            ],
        }
        metrics = {
            "fear_greed_value": round(value, 6),
            "fear_greed_delta_1d": round(delta, 6),
            "value_classification": classification,
            "previous_value": round(previous_value, 6) if previous else None,
            "previous_value_classification": previous_classification or None,
            "time_until_update_seconds": time_until_update,
        }
        summary = (
            f"Fear & Greed index is {value:.0f} ({classification})"
            f"{f', {delta:+.0f} vs prior day' if previous else ''}."
        )
        return SourceData(
            name=self.name,
            optional=self.optional,
            weight_hint=self.weight_hint,
            status="ok",
            fetched_at=fetched_at,
            url=url,
            raw_content=json.dumps(response.json(), ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            raw_extension="json",
            transport={"url": url, "http_status": response.status_code},
            metrics=metrics,
            heuristic=heuristic,
            summary=summary,
        )


def build_sources(config: dict[str, Any]) -> list[MarketSource]:
    sources: list[MarketSource] = []
    source_cfg = config.get("sources") or {}
    if not isinstance(source_cfg, dict):
        return sources
    mapping = {
        "forex_factory": ForexFactorySource,
        "coingecko": CoinGeckoSource,
        "coinmarketcap": CoinMarketCapSource,
        "fear_greed": FearGreedSource,
    }
    for name, klass in mapping.items():
        cfg = source_cfg.get(name) or {}
        if not isinstance(cfg, dict):
            continue
        if not bool(cfg.get("enabled", True)):
            continue
        sources.append(klass(name=name, config=cfg))
    return sources
