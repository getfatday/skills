# Copilot Money CLI — Test Plan

## Test Inventory

| File              | Category           | Est. Tests |
|-------------------|--------------------|-----------|
| `test_proto.py`   | Unit — protobuf    | ~15       |
| `test_keys.py`    | Unit — key parser  | ~10       |
| `test_cli.py`     | CLI smoke + E2E    | ~20       |
| **Total**         |                    | **~45**   |

## Unit Tests

### `test_proto.py` — Protobuf Wire-Format Parser

Tests use **synthetic byte sequences** — no real cache needed.

- Varint decoding: single-byte, multi-byte, negative (two's complement 64-bit)
- Tag decoding: field number + wire type extraction
- Value decoding by Firestore type:
  - String (field 17), boolean (field 1), integer (field 2, signed), double (field 3, fixed64)
  - Null (field 11), timestamp (field 10, sub-message with seconds + nanos)
  - Array (field 9), map (field 6)
- `skip_field` for each wire type (0, 1, 2, 5)
- `decode_document` edge cases: empty bytes returns None, malformed returns None
- `decode_document` with minimal valid MaybeDocument bytes

### `test_keys.py` — LevelDB Key Parser

Tests use **synthetic binary keys** — no real cache needed.

- `parse_key` on a valid remote_document key returns `("remote_document", [...])`
- `parse_key` on a collection_parent key returns None (in `_SKIP_TYPES`)
- `parse_key` on metadata key types (target, mutation_queue, etc.) returns None
- `parse_key` on empty bytes returns None
- `parse_key` on binary-only (no printable ASCII) returns None
- Segment extraction: verifies correct splitting on non-printable boundaries
- Short segment filtering behavior

## CLI Smoke Tests

All use `click.testing.CliRunner` against the `cli` group.

- `--help` exits 0, output contains "Copilot Money"
- `--version` exits 0, output contains "0.1.0"
- Each subcommand's `--help` exits 0: status, accounts, transactions, categories, budgets, recurring, summary

## E2E Tests (Real Cache)

**Hard dependency on local Copilot Money cache.** No mocking, no skipping.

### CliRunner E2E

- `status --format json` — valid JSON, contains `total_documents`
- `accounts --format json` — valid JSON list with at least one account
- `transactions --format json` — valid JSON list
- `transactions --start 2026-03-01 --format json` — filtered output, valid JSON
- `categories --format json` — valid JSON list
- `categories --flat --format json` — flat list, valid JSON
- `summary --format json` — valid JSON, contains `net_worth`
- `accounts --format table` — output contains column headers
- `transactions --format csv` — first line contains "date"

### Subprocess E2E

Validates the installed entry point works end-to-end via `subprocess.run`.

- `gfd-copilot-money --help` — exits 0, contains "Copilot Money"
- `gfd-copilot-money status --format json` — valid JSON with `total_documents`
- `gfd-copilot-money accounts --format json` — valid JSON list, non-empty

## Workflow Scenarios

Covered implicitly by E2E:

1. **Cache discovery** — every E2E test exercises the cache path lookup
2. **LevelDB open + iteration** — status/accounts/transactions all read the DB
3. **Protobuf decode pipeline** — keys parsed, documents decoded, models hydrated
4. **Output formatting** — JSON, table, and CSV formats all validated
5. **Date filtering** — transactions with `--start` validates the filter chain
