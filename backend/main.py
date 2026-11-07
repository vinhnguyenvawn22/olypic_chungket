from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Literal
import json
import mimetypes
import warnings
import uuid

import joblib
import numpy as np
import pandas as pd
import sklearn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sklearn.exceptions import InconsistentVersionWarning
from backend.advisory import Evidence, StatusRequest, advance, make_advisory, status as advisory_status, MIN_SAMPLES

ROOT = Path(__file__).resolve().parents[1]
# Windows may register .js as text/plain. Browsers reject ES modules with that MIME.
# Initialize first so a subsequent registry load cannot override these mappings.
mimetypes.init()
for extension, media_type in {'.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml'}.items():
    mimetypes.add_type(media_type, extension)
FEATURES = ['Temperature', 'Humidity', 'Light', 'CO2', 'HumidityRatio']
LOCAL_TZ = timezone(timedelta(hours=7))
MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS = 12000
ModelId = Literal['uneti15', 'btc']
SPECS = {
    'uneti15': ('UNETI15 · Logistic Regression cải tiến', ROOT / 'model/logistic_optimized.joblib'),
    'btc': ('BTC · Baseline', ROOT / 'outputs/AI04/model.joblib'),
}
registry: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app):
    registry.clear()
    for model_id, (name, path) in SPECS.items():
        item = {'id': model_id, 'name': name, 'available': False, 'error': None}
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', InconsistentVersionWarning)
                model = joblib.load(path)
            if list(model.feature_names_in_) != FEATURES:
                raise ValueError('Thứ tự đặc trưng không tương thích.')
            if set(model.classes_) != {0, 1}:
                raise ValueError('Mô hình không có đúng hai lớp 0 và 1.')
            params=model.get_params()
            item.update(available=True, model=model, occupied_index=list(model.classes_).index(1), parameters={k:v for k,v in params.items() if k.endswith('__degree') or k.endswith('__C') or k.endswith('__class_weight')})
        except Exception as exc:
            item['error'] = f'Không nạp được mô hình: {exc}'
        registry[model_id] = item
    yield
    registry.clear()


app = FastAPI(title='UNETI Smart Classroom', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'], allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])


@app.middleware('http')
async def limit_request(request, call_next):
    if request.method == 'POST':
        size = request.headers.get('content-length')
        if size and (not size.isdigit() or int(size) > MAX_BYTES + 65536):
            return JSONResponse(status_code=413, content={'detail': 'Giới hạn dữ liệu tải lên là 8 MB.'})
    return await call_next(request)


def timestamp(value: Any) -> datetime:
    if value is None or str(value).strip() == '':
        raise ValueError('Thời gian mẫu bị thiếu.')
    try:
        if not isinstance(value, (str, datetime, pd.Timestamp)):
            raise ValueError()
        parsed = pd.Timestamp(value)
        if pd.isna(parsed):
            raise ValueError()
        result = parsed.to_pydatetime()
        return result.replace(tzinfo=LOCAL_TZ) if result.tzinfo is None else result.astimezone(LOCAL_TZ)
    except Exception:
        raise ValueError('Thời gian không hợp lệ; dùng định dạng ISO hoặc YYYY-MM-DD HH:MM:SS.')


class Sensors(BaseModel):
    model_config = ConfigDict(extra='ignore', allow_inf_nan=False)
    Temperature: float = Field(ge=-273.15)
    Humidity: float = Field(ge=0, le=100)
    Light: float = Field(ge=0)
    CO2: float = Field(ge=0)
    HumidityRatio: float = Field(ge=0)

    @field_validator('*', mode='before')
    @classmethod
    def no_bool(cls, value):
        if isinstance(value, bool):
            raise ValueError('Giá trị phải là số, không phải boolean.')
        return value


class Context(BaseModel):
    count: int = Field(default=0, ge=0, le=1000000)
    last_timestamp: datetime | None = None
    evidence: list[Evidence] = Field(default_factory=list, max_length=MIN_SAMPLES)
    streak_started_at: datetime | None = None
    episode_id: str | None = Field(default=None, max_length=100)


class PredictRequest(BaseModel):
    model_id: ModelId = 'uneti15'
    compare: bool = False
    samples: list[dict[str, Any]] = Field(min_length=1, max_length=MAX_ROWS)
    context: dict[ModelId, Context] = Field(default_factory=dict)


def infer(req: PredictRequest):
    ids = [req.model_id] + ([i for i in SPECS if i != req.model_id] if req.compare else [])
    for mid in ids:
        if not registry.get(mid, {}).get('available'):
            raise HTTPException(503, registry.get(mid, {}).get('error') or f'Mô hình {mid} chưa sẵn sàng.')
    rows, valid_values, valid_indices = [], [], []
    for i, sample in enumerate(req.samples):
        row = {'row': i + 1, 'timestamp': None, 'sensors': None, 'error': None, 'results': {}, 'advisory': make_advisory()}
        try:
            when = timestamp(sample.get('date'))
            sensors = Sensors.model_validate(sample)
            row.update(timestamp=when.isoformat(), sensors=sensors.model_dump())
            valid_values.append(sensors.model_dump())
            valid_indices.append(i)
        except (ValueError, ValidationError) as exc:
            row['error'] = str(exc)
            row['advisory'] = make_advisory(invalid=True)
        rows.append(row)
    for mid in ids:
        entry = registry[mid]
        ctx = req.context.get(mid, Context())
        count, previous = ctx.count, ctx.last_timestamp
        episode_id = ctx.episode_id
        evidence = [{'timestamp': timestamp(e.timestamp).isoformat(), 'probability': e.probability} for e in ctx.evidence]
        started = timestamp(ctx.streak_started_at).isoformat() if ctx.streak_started_at else None
        predictions = {}
        if valid_values:
            frame = pd.DataFrame(valid_values, columns=FEATURES)
            try:
                probs = entry['model'].predict_proba(frame)[:, entry['occupied_index']]
                labels = entry['model'].predict(frame)
                if not np.isfinite(probs).all():
                    raise ValueError('Mô hình trả về xác suất không hữu hạn.')
                predictions = {i: (int(label), float(p)) for i, label, p in zip(valid_indices, labels, probs)}
            except Exception as exc:
                raise HTTPException(500, f'Lỗi suy luận {mid}: {exc}')
        for i, row in enumerate(rows):
            if row['error']:
                count, previous, evidence, started, episode_id = 0, None, [], None, None
                continue
            label, prob = predictions[i]
            current = timestamp(row['timestamp'])
            count, alert, reset = advance(prob, current, count, previous)
            if reset or count == 0:
                evidence, started, episode_id = [], None, None
            if count > 0:
                evidence = (evidence + [{'timestamp': current.isoformat(), 'probability': prob}])[-MIN_SAMPLES:]
                if count == 1 or started is None:
                    started = current.isoformat()
                if count == 1 or episode_id is None:
                    episode_id = f'{mid}:{uuid.uuid4().hex}'
            advisory = make_advisory(count, valid=True, evidence=list(evidence), reset_reason=reset, started_at=started, model_id=mid, episode_id=episode_id)
            row['results'][mid] = {'model_id': mid, 'label': label, 'probability': prob, 'count': count, 'alert': alert, 'reset_reason': reset, 'evidence': list(evidence), 'streak_started_at': started, 'advisory': advisory}
            if mid == req.model_id:
                row['advisory'] = advisory
            previous = current
    contexts = {}
    for mid in ids:
        final = rows[-1]
        contexts[mid] = {'count': final['results'][mid]['count'], 'last_timestamp': final['timestamp'], 'evidence': final['results'][mid]['evidence'], 'streak_started_at': final['results'][mid]['streak_started_at'], 'episode_id': final['results'][mid]['advisory']['episode_id']} if not final['error'] else {'count': 0, 'last_timestamp': None}
    return {'model_id': req.model_id, 'rows': rows, 'context': contexts, 'invalid_rows': sum(bool(r['error']) for r in rows)}


@app.post('/api/advisory/status')
def energy_status(req: StatusRequest):
    return advisory_status(req)


@app.get('/api/health')
def health():
    return {'status': 'ok', 'models_ready': sum(x['available'] for x in registry.values()), 'sklearn_version': sklearn.__version__}


@app.get('/api/models')
def models():
    result = []
    for mid, entry in registry.items():
        info = {k: v for k, v in entry.items() if k not in ('model', 'occupied_index')}
        metric_path = ROOT / ('model/logistic_optimized_metadata.json' if mid == 'uneti15' else 'outputs/AI04/metrics.json')
        try:
            info['evaluation'] = json.loads(metric_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            info['evaluation'] = None
        result.append(info)
    return {'default': 'uneti15', 'models': result}


@app.post('/api/predict')
def predict(req: PredictRequest):
    if len(req.samples) != 1:
        raise HTTPException(422, 'Endpoint này nhận đúng một mẫu.')
    result = infer(req)
    if result['invalid_rows']:
        raise HTTPException(422, result['rows'][0]['error'])
    return result


@app.post('/api/predict-batch')
def predict_batch(req: PredictRequest):
    return infer(req)


@app.post('/api/upload')
def upload(file: UploadFile = File(...), model_id: ModelId = Form('uneti15'), compare: bool = Form(False)):
    if Path(file.filename or '').suffix.lower() not in ('.csv', '.txt'):
        raise HTTPException(422, 'Chỉ nhận tệp .csv hoặc .txt dạng CSV.')
    content = file.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(413, 'Tệp vượt quá 8 MB.')
    try:
        frame = pd.read_csv(StringIO(content.decode('utf-8-sig')), nrows=MAX_ROWS + 1)
    except Exception as exc:
        raise HTTPException(422, f'Không đọc được CSV UTF-8: {exc}')
    if frame.empty or len(frame) > MAX_ROWS:
        raise HTTPException(422, f'CSV cần từ 1 đến {MAX_ROWS} mẫu.')
    missing = set(FEATURES) - set(frame.columns)
    if missing:
        raise HTTPException(422, f'Thiếu cột: {", ".join(sorted(missing))}')
    assumed = 'date' not in frame.columns
    if assumed:
        frame['date'] = pd.date_range(datetime.now(LOCAL_TZ), periods=len(frame), freq='1min').astype(str)
    samples = frame[FEATURES + ['date']].astype(object).where(pd.notna(frame[FEATURES + ['date']]), None).to_dict('records')
    return {**infer(PredictRequest(model_id=model_id, compare=compare, samples=samples)), 'assumed_timestamps': assumed, 'source': file.filename}


@app.get('/api/scenarios/{scenario}')
def scenario(scenario: Literal['observe', 'empty', 'occupied', 'compare', 'gap']):
    # Deliberately read only training data; reserved datatest2 is never opened.
    frame = pd.read_csv(ROOT / 'data/AI04/datatraining.txt')
    if scenario in ('empty', 'gap', 'occupied'):
        matching = frame['Occupancy'].eq(1 if scenario == 'occupied' else 0)
        starts = np.flatnonzero(matching.rolling(8).sum().eq(8).to_numpy())
        if not len(starts):
            raise HTTPException(500, 'Không có đoạn dữ liệu phù hợp.')
        start = int(starts[0]) - 7
        selected = frame.iloc[start:start + 8].copy()
    else:
        selected = frame.iloc[:24 if scenario == 'compare' else 1].copy()
    if scenario == 'gap':
        dates = pd.to_datetime(selected['date'])
        dates.iloc[3:] += pd.Timedelta(minutes=5)
        selected['date'] = dates.astype(str)
    return {'samples': selected[FEATURES + ['date']].to_dict('records'), 'description': 'Cảm biến từ datatraining.txt' + ('; thời gian gián đoạn giả lập +5 phút từ mẫu 4.' if scenario == 'gap' else '; giữ nguyên thứ tự mẫu.'), 'simulated': scenario == 'gap'}


if (ROOT / 'frontend/dist').exists():
    app.mount('/', StaticFiles(directory=ROOT / 'frontend/dist', html=True), name='frontend')
