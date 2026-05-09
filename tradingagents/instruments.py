import re
from dataclasses import asdict, dataclass
from typing import Any, Dict

from tradingagents.dataflows.utils import safe_ticker_component


_COINGECKO_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,98}[a-z0-9]$")


@dataclass(frozen=True)
class ResolvedInstrument:
    asset_class: str
    identifier: str
    coin_id: str | None
    quote_currency: str | None
    display_label: str
    safe_storage_key: str

    def to_state(self) -> Dict[str, Any]:
        return asdict(self)


def validate_coingecko_id(coin_id: str) -> str:
    if not isinstance(coin_id, str):
        raise ValueError("CoinGecko id must be a string")
    normalized = coin_id.strip().lower()
    if not _COINGECKO_ID_RE.fullmatch(normalized):
        raise ValueError(
            "Invalid CoinGecko id. Use the exact lowercase CoinGecko id, such as 'bitcoin', 'ethereum', or 'solana'."
        )
    return normalized


def resolve_instrument(identifier: str, config: Dict[str, Any]) -> ResolvedInstrument:
    asset_class = config.get("asset_class", "equity")
    if asset_class == "crypto":
        coin_id = validate_coingecko_id(identifier)
        quote_currency = str(config.get("crypto_quote_currency", "usd")).strip().lower()
        safe_key = safe_ticker_component(f"crypto-{coin_id}", max_len=128)
        return ResolvedInstrument(
            asset_class="crypto",
            identifier=coin_id,
            coin_id=coin_id,
            quote_currency=quote_currency,
            display_label=f"{coin_id}/{quote_currency}",
            safe_storage_key=safe_key,
        )
    safe_key = safe_ticker_component(identifier)
    return ResolvedInstrument(
        asset_class="equity",
        identifier=identifier,
        coin_id=None,
        quote_currency=None,
        display_label=identifier,
        safe_storage_key=safe_key,
    )
