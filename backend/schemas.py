"""Bentuk respons API (dipakai untuk validasi keluaran dan dokumentasi /docs)."""

from typing import Literal

from pydantic import BaseModel


class MemberState(BaseModel):
    token: str
    points_total: int
    deposits_today: int
    daily_limit: int
    remaining_today: int


class BinState(BaseModel):
    bin_id: str
    location: str
    capacity_g: float
    current_g: float
    fill_pct: float
    status: str
    accepting: bool


class VerifyResponse(BaseModel):
    decision: Literal["ACCEPT", "REJECT"]
    reason_code: str
    reason_text: str
    signals: dict
    points_awarded: int
    member: MemberState
    transaction_id: int
    bin: BinState


class Item(BaseModel):
    item_id: str
    label: str
    photo: str
    photo_url: str
    barcode: str | None
    barcode_image_url: str | None
    weight_g: float
    ground_truth: str
    expected_decision: Literal["ACCEPT", "REJECT"]
    expected_reason: str | None = None
    scenario: str


class Transaction(BaseModel):
    id: int
    ts: str
    bin_id: str
    member_token: str
    claimed_product_id: str | None
    photo_class: str | None
    photo_conf: float | None
    barcode_present: bool
    barcode_valid: bool
    weight_g: float | None
    decision: Literal["ACCEPT", "REJECT"]
    reason_code: str
    photo_path: str | None


class Alert(BaseModel):
    id: int
    ts: str
    bin_id: str
    type: str
    detail: str | None
    resolved: bool


class Heartbeat(BaseModel):
    device_id: str
    rssi: int | None = None
    uptime_s: int | None = None
    firmware: str | None = None
    ip: str | None = None


class Stats(BaseModel):
    totals: dict
    accepted_by_product: list[dict]
    rejected_by_reason: list[dict]
    bins: list[BinState]
