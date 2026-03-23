"""Query and deduplication layer for Copilot Money cache data."""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Any

from gfd_copilot_money_cli.core.db import find_cache_dir, open_db
from gfd_copilot_money_cli.core.keys import parse_key
from gfd_copilot_money_cli.core.models import Account, Budget, Category, Recurring, Transaction
from gfd_copilot_money_cli.core.proto import decode_document


def load_all() -> dict[str, list[tuple[str, dict[str, Any]]]]:
    """Load all documents from the cache, grouped by collection.

    Returns a dict mapping collection name to a list of (doc_id, fields) tuples.
    """
    db = open_db()
    collections: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)

    for key, value in db:
        result = parse_key(key)
        if result is None:
            continue
        key_type, segments = result
        if key_type != "remote_document" or not value:
            continue
        if len(segments) < 2:
            continue

        collection = segments[-2]
        doc_id = segments[-1]

        try:
            fields = decode_document(value)
        except Exception:
            continue
        if fields is None:
            continue

        collections[collection].append((doc_id, fields))

    db.close()
    return dict(collections)


def _dedup_transactions(docs: list[tuple[str, dict[str, Any]]]) -> list[Transaction]:
    """Deduplicate transactions.

    1. Group by transaction_id, keep the last occurrence (latest).
    2. If a non-pending transaction exists whose pending_transaction_id
       matches a pending transaction's transaction_id, drop the pending one.
    """
    txns: list[Transaction] = []
    for doc_id, fields in docs:
        try:
            txns.append(Transaction.from_doc(doc_id, fields))
        except Exception:
            continue

    if not txns:
        return []

    # Step 1: Group by transaction_id, keep latest (last seen)
    by_id: dict[str, Transaction] = {}
    for t in txns:
        by_id[t.transaction_id] = t

    # Step 2: Collect pending_transaction_ids from non-pending transactions
    resolved_pending_ids: set[str] = set()
    for t in by_id.values():
        if not t.pending and t.pending_transaction_id:
            resolved_pending_ids.add(t.pending_transaction_id)

    # Step 3: Drop pending transactions that have been resolved
    result: list[Transaction] = []
    for t in by_id.values():
        if t.pending and t.transaction_id in resolved_pending_ids:
            continue
        result.append(t)

    return result


def get_transactions(
    *,
    account_id: str | None = None,
    category_id: str | None = None,
    pending: bool | None = None,
    excluded: bool | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[Transaction]:
    """Get deduplicated transactions with optional filters."""
    all_docs = load_all()
    docs = all_docs.get("transactions", [])
    txns = _dedup_transactions(docs)

    if account_id is not None:
        txns = [t for t in txns if t.account_id == account_id]
    if category_id is not None:
        txns = [t for t in txns if t.category_id == category_id]
    if pending is not None:
        txns = [t for t in txns if t.pending == pending]
    if excluded is not None:
        txns = [t for t in txns if t.excluded == excluded]
    if start_date is not None:
        txns = [t for t in txns if t.date >= start_date]
    if end_date is not None:
        txns = [t for t in txns if t.date <= end_date]

    return txns


def get_accounts(*, type_filter: str | None = None) -> list[Account]:
    """Get all accounts, optionally filtered by account type."""
    all_docs = load_all()
    docs = all_docs.get("accounts", [])

    accounts: list[Account] = []
    for doc_id, fields in docs:
        try:
            accounts.append(Account.from_doc(doc_id, fields))
        except Exception:
            continue

    if type_filter is not None:
        type_lower = type_filter.lower()
        accounts = [a for a in accounts if a.account_type.lower() == type_lower]

    return accounts


def get_categories() -> list[Category]:
    """Get all categories."""
    all_docs = load_all()
    docs = all_docs.get("categories", [])

    categories: list[Category] = []
    for doc_id, fields in docs:
        try:
            categories.append(Category.from_doc(doc_id, fields))
        except Exception:
            continue

    return categories


def get_budgets() -> list[Budget]:
    """Get all budgets."""
    all_docs = load_all()
    docs = all_docs.get("budgets", [])

    budgets: list[Budget] = []
    for doc_id, fields in docs:
        try:
            budgets.append(Budget.from_doc(doc_id, fields))
        except Exception:
            continue

    return budgets


def get_recurring() -> list[Recurring]:
    """Get all recurring transactions."""
    all_docs = load_all()

    # Try both possible collection names
    docs: list[tuple[str, dict[str, Any]]] = []
    for name in ("recurring", "recurring_transactions", "recurrings"):
        docs.extend(all_docs.get(name, []))

    recurring: list[Recurring] = []
    for doc_id, fields in docs:
        try:
            recurring.append(Recurring.from_doc(doc_id, fields))
        except Exception:
            continue

    return recurring


def get_stats() -> dict[str, Any]:
    """Get statistics about the cache: counts per collection, path, and size."""
    try:
        cache_dir = find_cache_dir()
    except FileNotFoundError:
        return {"error": "Cache not found", "collections": {}}

    # Calculate total size
    total_size = 0
    for dirpath, _dirnames, filenames in os.walk(cache_dir):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total_size += os.path.getsize(fp)
            except OSError:
                pass

    all_docs = load_all()
    collection_counts = {name: len(docs) for name, docs in sorted(all_docs.items())}

    return {
        "cache_path": cache_dir,
        "cache_size_bytes": total_size,
        "cache_size_mb": round(total_size / (1024 * 1024), 2),
        "total_documents": sum(collection_counts.values()),
        "collections": collection_counts,
    }
