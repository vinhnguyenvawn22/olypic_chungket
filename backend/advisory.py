"""Authoritative advisory states and device guidance; never controls real devices."""
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

THRESHOLD = .20
MIN_SAMPLES = 3
MAX_GAP_SECONDS = 120
LOCAL_TZ = timezone(timedelta(hours=7))


def local(value: datetime) -> datetime:
    return value.replace(tzinfo=LOCAL_TZ) if value.tzinfo is None else value.astimezone(LOCAL_TZ)


def advance(probability: float, current: datetime, count: int, previous: datetime | None):
    reason = None
    if previous is not None:
        gap = (local(current) - local(previous)).total_seconds()
        if gap <= 0 or gap > MAX_GAP_SECONDS:
            count = 0
            reason = 'Thời gian không tăng' if gap <= 0 else 'Gián đoạn quá 120 giây'
    count = count + 1 if probability < THRESHOLD else 0
    return count, count >= MIN_SAMPLES, reason


class Evidence(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    timestamp: datetime
    probability: float = Field(ge=0, le=1)


class Snapshot(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    model_id: Literal['uneti15', 'btc']
    probability: float = Field(ge=0, le=1)
    count: int = Field(ge=0, le=1000000)
    reset_reason: str | None = None
    evidence: list[Evidence] = Field(default_factory=list, max_length=MIN_SAMPLES)
    streak_started_at: datetime | None = None
    episode_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode='after')
    def consistent(self):
        if (self.probability >= THRESHOLD) != (self.count == 0):
            raise ValueError('Bộ đếm không phù hợp với xác suất đã suy luận.')
        return self


class DeviceConfirmation(BaseModel):
    state: Literal['unknown', 'on', 'off'] = 'unknown'
    confirmed_at: datetime | None = None


class Review(BaseModel):
    seen_at: datetime | None = None
    room: Literal['unknown', 'occupied', 'empty'] = 'unknown'
    checked_at: datetime | None = None
    devices: dict[Literal['lights', 'fan', 'screen'], DeviceConfirmation] = Field(default_factory=dict)


class StatusRequest(BaseModel):
    mode: Literal['manual', 'csv'] = 'manual'
    timestamp: datetime | None = None
    prediction: Snapshot | None = None
    invalid: bool = False
    review: Review = Field(default_factory=Review)


def make_advisory(count=0, *, valid=False, invalid=False, evidence=None, reset_reason=None, started_at=None, model_id=None, episode_id=None):
    state = 'invalid' if invalid else 'no_data' if not valid else 'monitoring' if count == 0 else 'advisory' if count >= MIN_SAMPLES else 'verifying'
    code = {'invalid': 'invalid_sample', 'no_data': 'awaiting_sample', 'monitoring': 'probability_at_or_above_threshold', 'advisory': 'consecutive_low_probability', 'verifying': 'collecting_samples'}[state]
    titles = {'no_data': 'Chưa có dữ liệu', 'invalid': 'Chuỗi bị ngắt', 'monitoring': 'Đang theo dõi', 'advisory': 'Cần kiểm tra thiết bị điện', 'verifying': f'Đang xác nhận · {count}/{MIN_SAMPLES}'}
    summaries = {
        'no_data': 'Phân tích một mẫu hoặc nạp chuỗi dữ liệu để bắt đầu.',
        'invalid': 'Dữ liệu hoặc yêu cầu không hợp lệ. Chuỗi xác nhận đã ngắt; cần mẫu hợp lệ mới.',
        'monitoring': 'P(có người) chưa dưới ngưỡng khuyến nghị. Chưa đề xuất kiểm tra điện từ mẫu này.',
        'verifying': f'Đã có {count} mẫu liên tiếp dưới ngưỡng. Chờ đủ {MIN_SAMPLES} mẫu trước khi đề xuất kiểm tra.',
        'advisory': f'Đã có {count} mẫu liên tiếp có P(có người) < {THRESHOLD:.0%}. Kiểm tra thực tế phòng và thiết bị trước khi hành động.',
    }
    return {'state': state, 'code': code, 'title': titles[state], 'summary': summaries[state], 'count': count if valid else 0,
            'eligible': state == 'advisory', 'threshold': THRESHOLD, 'required_samples': MIN_SAMPLES, 'max_gap_seconds': MAX_GAP_SECONDS,
            'reset_reason': reset_reason, 'evidence': evidence or [], 'streak_started_at': started_at,
            'episode_id': episode_id or (f'{model_id}:{started_at}' if started_at else None)}


DEVICE_NAMES = {'lights': 'Đèn trần', 'fan': 'Quạt trần', 'screen': 'Màn hình bàn giáo viên'}


def status(req: StatusRequest, *, now: datetime | None = None):
    now = local(now or datetime.now(LOCAL_TZ))
    pred = req.prediction
    valid = pred is not None and req.timestamp is not None and not req.invalid
    result = make_advisory(
        pred.count if valid else 0, valid=valid, invalid=req.invalid,
        evidence=[{'timestamp': local(e.timestamp).isoformat(), 'probability': e.probability} for e in pred.evidence] if valid else [],
        reset_reason=pred.reset_reason if valid else None,
        started_at=local(pred.streak_started_at).isoformat() if valid and pred.streak_started_at else None,
        model_id=pred.model_id if pred else None, episode_id=pred.episode_id if valid else None,
    )
    expires = local(req.timestamp) + timedelta(seconds=MAX_GAP_SECONDS) if valid and req.mode == 'manual' else None
    if expires is not None and now > expires:
        result.update(state='stale', code='manual_sample_expired', title='Dữ liệu đã cũ', summary='Không có mẫu nhập tay mới trong thời gian cho phép. Khuyến nghị trước chỉ còn là lịch sử; cần phân tích mẫu mới.', eligible=False, count=0)
    result.update(source_mode=req.mode, sample_timestamp=local(req.timestamp).isoformat() if req.timestamp else None,
                  server_time=now.isoformat(), expires_at=expires.isoformat() if expires else None,
                  refresh_after_seconds=max(.01, (expires-now).total_seconds()) if expires and result['state'] != 'stale' else None)
    result['review'] = req.review.model_dump(mode='json')
    actions = []
    for device, name in DEVICE_NAMES.items():
        confirmation = req.review.devices.get(device, DeviceConfirmation())
        if not result['eligible']:
            message = 'Chưa có khuyến nghị tiết kiệm điện hiện hành. Tiếp tục theo dõi dữ liệu.'
        elif req.review.room == 'occupied':
            message = 'Bạn xác nhận phòng còn người. Giữ thiết bị theo nhu cầu; không dùng đề xuất AI để tắt điện.'
        elif confirmation.state == 'off':
            message = 'Theo xác nhận của bạn, thiết bị đã tắt. Chưa cần xử lý thêm đối với thiết bị này.'
        elif req.review.room == 'unknown':
            message = 'Kiểm tra phòng còn người hay không trước khi quyết định về thiết bị.'
        elif confirmation.state == 'on':
            message = 'Bạn xác nhận phòng đã trống và thiết bị đang bật. Kiểm tra nhu cầu sử dụng; xem xét tắt theo quy trình của phòng.'
        else:
            message = 'Bạn xác nhận phòng đã trống. Kiểm tra thiết bị đang bật hay tắt trước khi quyết định.'
        actions.append({'id': device, 'name': name, 'state': confirmation.state, 'confirmed_at': confirmation.confirmed_at.isoformat() if confirmation.confirmed_at else None, 'message': message})
    result['device_actions'] = actions
    return result
