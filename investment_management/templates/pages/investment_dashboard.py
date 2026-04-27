from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime
from typing import Any

import frappe


DATE_FORMAT = "%Y-%m-%d"


def _as_date(value: str | date | datetime | None) -> date | None:
	if not value:
		return None
	if isinstance(value, datetime):
		return value.date()
	if isinstance(value, date):
		return value
	return datetime.strptime(value, DATE_FORMAT).date()


def _format_month(value: str | date | datetime | None) -> str:
	parsed = _as_date(value)
	if not parsed:
		return "Unknown"
	return parsed.strftime("%b %Y")


def get_context(context: dict[str, Any]) -> dict[str, Any]:
	investments = frappe.get_all(
		"Investment",
		fields=[
			"name",
			"investor",
			"investment_date",
			"investment_amount",
			"total_value",
			"expected_roi",
			"status",
			"investment_type",
			"project",
		],
		order_by="investment_date desc",
	)

	investment_names = [investment.name for investment in investments]
	ledger_entries = []
	if investment_names:
		ledger_entries = frappe.get_all(
			"Investment Ledger",
			filters={"parent": ["in", investment_names], "parenttype": "Investment"},
			fields=["parent", "date", "type", "amount"],
			order_by="date desc",
		)

	total_invested = sum((investment.investment_amount or 0) for investment in investments)
	total_current_value = sum((investment.total_value or investment.investment_amount or 0) for investment in investments)
	total_withdrawals = sum(
		(entry.amount or 0) for entry in ledger_entries if entry.type == "Withdrawal"
	)
	estimated_dividend = sum(
		((investment.investment_amount or 0) * (investment.expected_roi or 0) / 100)
		for investment in investments
	)

	monthly_totals: dict[str, float] = defaultdict(float)
	type_totals: dict[str, float] = defaultdict(float)
	status_totals: dict[str, float] = defaultdict(float)

	for investment in investments:
		month_key = _format_month(investment.investment_date)
		amount = investment.investment_amount or 0
		monthly_totals[month_key] += amount
		type_totals[investment.investment_type or "Unspecified"] += amount
		status_totals[investment.status or "Unknown"] += amount

	history = []
	for investment in investments:
		history.append(
			{
				"date": _as_date(investment.investment_date),
				"label": "Investment created",
				"investment": investment.name,
				"amount": investment.investment_amount or 0,
				"type": investment.investment_type or "Unspecified",
			}
		)

	for entry in ledger_entries:
		history.append(
			{
				"date": _as_date(entry.date),
				"label": entry.type,
				"investment": entry.parent,
				"amount": entry.amount or 0,
				"type": "Ledger",
			}
		)

	history = sorted(history, key=lambda item: item["date"] or date.min, reverse=True)[:30]

	dashboard_data = {
		"summary": {
			"total_invested": total_invested,
			"total_current_value": total_current_value,
			"total_withdrawals": total_withdrawals,
			"estimated_dividend": estimated_dividend,
			"active_investments": len([item for item in investments if item.status == "Active"]),
			"closed_investments": len([item for item in investments if item.status == "Closed"]),
		},
		"monthly_totals": [
			{"label": key, "value": value} for key, value in monthly_totals.items()
		],
		"type_totals": [{"label": key, "value": value} for key, value in type_totals.items()],
		"status_totals": [{"label": key, "value": value} for key, value in status_totals.items()],
		"history": [
			{
				"date": item["date"].isoformat() if item["date"] else "",
				"label": item["label"],
				"investment": item["investment"],
				"amount": item["amount"],
				"type": item["type"],
			}
			for item in history
		],
	}

	context.title = "Investment Dashboard"
	context.no_cache = 1
	context.dashboard_data = json.dumps(dashboard_data)
	return context
