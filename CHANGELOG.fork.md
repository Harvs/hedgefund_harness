# Changelog

All notable changes to TradingAgents are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Breaking changes within the 0.x line are called out explicitly.

## [0.2.5] — 2026-05-09

### Added

- **Cryptocurrency support** via CoinGecko integration. Framework now supports both
  equity and crypto asset classes with unified instrument resolution. CLI prompts
  for asset class selection (equity/crypto) and validates CoinGecko IDs for crypto
  assets. (#crypto)
- **CoinGecko data vendor** — OHLCV data, technical indicators, and tokenomics
  for cryptocurrency analysis. Implements caching, rate-limit handling, and
  benchmark comparison against configurable crypto benchmark (default: bitcoin).
- **Instrument resolution module** (`tradingagents/instruments.py`) — unified
  `ResolvedInstrument` dataclass with safe storage keys, display labels, and
  asset class metadata. Supports both equity tickers and CoinGecko IDs.
- **Returns fetching module** (`tradingagents/returns.py`) — extracted from
  trading graph, now supports both equity (yfinance) and crypto (CoinGecko) with
  benchmark comparison. Handles raw returns, alpha vs benchmark, and holding days.
- **External context infrastructure** — minimal `external_context` field added to
  `AgentState` and propagated through the graph. Allows API wrappers to format
  caller-provided portfolio context, external news, social signals, and research
  summaries into a single prompt block treated as untrusted evidence.
- **`build_external_context_instruction()`** utility — formats external context
  into agent prompts with explicit guidance to treat as untrusted evidence and
  discuss conflicts with tool data.
- **FastAPI wrapper guide** — comprehensive documentation for building HTTP API
  service around `TradingAgentsGraph`, including request schemas, context
  formatting, Docker configuration, and example API calls. (#docs)

### Changed

- **Trading graph propagation** — `create_initial_state()` now accepts
  `instrument` and `external_context` parameters. `propagate()` accepts
  `external_context` and forwards it through the graph execution.
- **Agent prompts** — market, fundamentals, news, and social media analysts,
  trader, portfolio manager, and aggressive/conservative/neutral risk debators
  include external context in their prompts when provided.
- **Dataflow interface routing** — crypto-specific methods (get_stock_data,
  get_indicators, get_fundamentals) route to CoinGecko when `asset_class` is
  "crypto", bypassing equity vendor fallback chain.
- **Checkpoint and memory log keys** — now use `instrument.safe_storage_key`
  instead of raw ticker identifier, ensuring consistent keys across equity and
  crypto assets.

### Fixed

- **CoinGecko public API limit** — enforced 365-day limit on market chart range
  requests with proper error handling for date range violations. (#fix-coingecko)
- **Crypto indicator formatting** — replaced pandas `to_markdown()` with manual
  table formatting in `get_crypto_indicators_window` to avoid dependency issues.

### Test

- **Cryptocurrency capability tests** — comprehensive test suite for CoinGecko ID
  validation, instrument resolution, crypto vendor routing, tokenomics formatting,
  and returns calculation with benchmark comparison.
- **Docker test infrastructure** — added test stage to Dockerfile and tests service
  to docker-compose.yml with pytest support for running tests in containerized
  environment.

### Contributors

- Fork development — cryptocurrency support, external context infrastructure,
  and API wrapper documentation.

[0.2.5]: https://github.com/TauricResearch/TradingAgents/compare/v0.2.4...v0.2.5
