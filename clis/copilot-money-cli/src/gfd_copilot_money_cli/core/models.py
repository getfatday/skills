"""Dataclass models for Copilot Money entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _str(fields: dict[str, Any], *keys: str, default: str = "") -> str:
    """Look up the first matching key, return as string."""
    for k in keys:
        v = fields.get(k)
        if v is not None:
            return str(v)
    return default


def _float(fields: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    """Look up the first matching key, return as float."""
    for k in keys:
        v = fields.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return default


def _bool(fields: dict[str, Any], *keys: str, default: bool = False) -> bool:
    """Look up the first matching key, return as bool."""
    for k in keys:
        v = fields.get(k)
        if v is not None:
            return bool(v)
    return default


@dataclass
class Transaction:
    doc_id: str
    transaction_id: str = ""
    amount: float = 0.0
    date: str = ""
    name: str = ""
    original_name: str = ""
    account_id: str = ""
    category_id: str = ""
    pending: bool = False
    excluded: bool = False
    internal_transfer: bool = False
    transaction_type: str = ""
    payment_method: str = ""
    pending_transaction_id: str = ""
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_doc(cls, doc_id: str, fields: dict[str, Any]) -> Transaction:
        return cls(
            doc_id=doc_id,
            transaction_id=_str(fields, "transactionId", "transaction_id", default=doc_id),
            amount=_float(fields, "amount"),
            date=_str(fields, "date", "transactionDate"),
            name=_str(fields, "name", "displayName", "merchantName"),
            original_name=_str(fields, "originalName", "original_name"),
            account_id=_str(fields, "accountId", "account_id"),
            category_id=_str(fields, "categoryId", "category_id"),
            pending=_bool(fields, "pending"),
            excluded=_bool(fields, "excluded", "isExcluded"),
            internal_transfer=_bool(fields, "isInternalTransfer", "internal_transfer"),
            transaction_type=_str(fields, "transactionType", "transaction_type"),
            payment_method=_str(fields, "paymentMethod", "payment_method"),
            pending_transaction_id=_str(fields, "pendingTransactionId", "pending_transaction_id"),
            raw=fields,
        )


@dataclass
class Account:
    doc_id: str
    account_id: str = ""
    name: str = ""
    institution_name: str = ""
    account_type: str = ""
    account_subtype: str = ""
    current_balance: float = 0.0
    available_balance: float = 0.0
    currency: str = "USD"
    is_hidden: bool = False
    is_closed: bool = False
    mask: str = ""
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_doc(cls, doc_id: str, fields: dict[str, Any]) -> Account:
        return cls(
            doc_id=doc_id,
            account_id=_str(fields, "accountId", "account_id", default=doc_id),
            name=_str(fields, "name", "displayName", "accountName"),
            institution_name=_str(fields, "institutionName", "institution_name", "institution"),
            account_type=_str(fields, "accountType", "account_type", "type"),
            account_subtype=_str(fields, "accountSubtype", "account_subtype", "subtype"),
            current_balance=_float(fields, "currentBalance", "current_balance", "balance"),
            available_balance=_float(fields, "availableBalance", "available_balance"),
            currency=_str(fields, "currency", "isoCurrencyCode", default="USD"),
            is_hidden=_bool(fields, "isHidden", "is_hidden"),
            is_closed=_bool(fields, "isClosed", "is_closed"),
            mask=_str(fields, "mask"),
            raw=fields,
        )


@dataclass
class Category:
    doc_id: str
    category_id: str = ""
    name: str = ""
    icon: str = ""
    group: str = ""
    is_system: bool = False
    is_hidden: bool = False
    order: int = 0
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_doc(cls, doc_id: str, fields: dict[str, Any]) -> Category:
        return cls(
            doc_id=doc_id,
            category_id=_str(fields, "categoryId", "category_id", default=doc_id),
            name=_str(fields, "name", "displayName"),
            icon=_str(fields, "icon", "emoji"),
            group=_str(fields, "group", "categoryGroup", "category_group"),
            is_system=_bool(fields, "isSystem", "is_system"),
            is_hidden=_bool(fields, "isHidden", "is_hidden"),
            order=int(_float(fields, "order", "sortOrder", "sort_order")),
            raw=fields,
        )


@dataclass
class Budget:
    doc_id: str
    budget_id: str = ""
    category_id: str = ""
    amount: float = 0.0
    period: str = ""
    start_date: str = ""
    end_date: str = ""
    is_recurring: bool = False
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_doc(cls, doc_id: str, fields: dict[str, Any]) -> Budget:
        return cls(
            doc_id=doc_id,
            budget_id=_str(fields, "budgetId", "budget_id", default=doc_id),
            category_id=_str(fields, "categoryId", "category_id"),
            amount=_float(fields, "amount", "budgetAmount", "budget_amount"),
            period=_str(fields, "period", "budgetPeriod", "budget_period"),
            start_date=_str(fields, "startDate", "start_date"),
            end_date=_str(fields, "endDate", "end_date"),
            is_recurring=_bool(fields, "isRecurring", "is_recurring"),
            raw=fields,
        )


@dataclass
class Recurring:
    doc_id: str
    recurring_id: str = ""
    name: str = ""
    amount: float = 0.0
    frequency: str = ""
    category_id: str = ""
    account_id: str = ""
    next_date: str = ""
    is_active: bool = True
    is_income: bool = False
    raw: dict = field(default_factory=dict, repr=False)

    @classmethod
    def from_doc(cls, doc_id: str, fields: dict[str, Any]) -> Recurring:
        return cls(
            doc_id=doc_id,
            recurring_id=_str(fields, "recurringId", "recurring_id", default=doc_id),
            name=_str(fields, "name", "displayName", "merchantName"),
            amount=_float(fields, "amount"),
            frequency=_str(fields, "frequency", "recurrence", "period"),
            category_id=_str(fields, "categoryId", "category_id"),
            account_id=_str(fields, "accountId", "account_id"),
            next_date=_str(fields, "nextDate", "next_date", "nextExpectedDate"),
            is_active=_bool(fields, "isActive", "is_active", default=True),
            is_income=_bool(fields, "isIncome", "is_income"),
            raw=fields,
        )
