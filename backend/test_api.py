from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest
import joblib
from fastapi.testclient import TestClient

from backend.main import FEATURES, ROOT, advance, app, registry


@pytest.fixture(scope='module')
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def samples():
    return pd.read_csv(ROOT / 'data/AI04/datatraining.txt').head(8)[FEATURES + ['date']].to_dict('records')


def test_only_two_models_available(client):
    body = client.get('/api/models').json()
    assert body['default'] == 'uneti15'
    assert {m['id'] for m in body['models']} == {'btc', 'uneti15'}
    assert all(m['available'] for m in body['models'])
    assert client.get('/api/health').json()['models_ready'] == 2


def test_production_assets_have_browser_compatible_mime_types(client):
    """ES modules must load even when Windows associates .js with text/plain."""
    from html.parser import HTMLParser

    class AssetParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.assets = []

        def handle_starttag(self, tag, attrs):
            for key, value in attrs:
                if key in ('src', 'href') and value and value.startswith('/assets/'):
                    self.assets.append(value)

    if not (ROOT / 'frontend/dist/index.html').exists():
        pytest.skip('Build frontend before checking production asset headers.')
    page = client.get('/')
    assert page.status_code == 200
    parser = AssetParser()
    parser.feed(page.text)
    assert any(path.endswith('.js') for path in parser.assets)
    for path in parser.assets:
        response = client.get(path)
        assert response.status_code == 200
        expected = 'text/javascript' if path.endswith('.js') else 'text/css'
        assert response.headers['content-type'].split(';')[0] == expected


@pytest.mark.parametrize('model_id', ['btc', 'uneti15'])
def test_api_matches_saved_pipeline(client, samples, model_id):
    response = client.post('/api/predict-batch', json={'model_id': model_id, 'samples': samples})
    assert response.status_code == 200
    result = response.json()
    if model_id == 'uneti15':
        bundle = joblib.load(ROOT / 'model/improvement_bundle.joblib')
        frame = pd.DataFrame(samples)
        frame['date'] = pd.to_datetime(frame['date'])
        expected = bundle['models'][bundle['lock']['model']].score(frame)
    else:
        model = registry[model_id]['model']
        expected = model.predict_proba(pd.DataFrame(samples)[FEATURES])[:, list(model.classes_).index(1)]
    actual = [row['results'][model_id]['probability'] for row in result['rows']]
    np.testing.assert_allclose(actual, expected, rtol=1e-12)


def test_advisory_boundaries():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    count = 0
    for i in range(3):
        count, alert, _ = advance(.19, now + timedelta(seconds=60 * i), count, now + timedelta(seconds=60 * (i - 1)) if i else None)
        assert alert is (i == 2)
    assert advance(.20, now, 4, None)[:2] == (0, False)
    assert advance(.1, now + timedelta(seconds=120), 2, now)[:2] == (3, True)
    assert advance(.1, now + timedelta(seconds=121), 2, now)[:2] == (1, False)
    assert advance(.1, now, 2, now)[:2] == (1, False)
    assert advance(.1, now - timedelta(seconds=1), 2, now)[:2] == (1, False)


def test_comparison_and_contexts(client):
    samples = client.get('/api/scenarios/empty').json()['samples']
    response = client.post('/api/predict-batch', json={'samples': samples, 'compare': True}).json()
    assert set(response['context']) == {'btc', 'uneti15'}
    for mid in ('btc', 'uneti15'):
        assert response['rows'][2]['results'][mid]['alert']
    # No implicit cross-model/session context.
    fresh = client.post('/api/predict', json={'model_id': 'btc', 'samples': samples[:1]}).json()
    assert fresh['rows'][0]['results']['btc']['count'] == 1
    continued = client.post('/api/predict', json={'samples': samples[1:2], 'context': {'uneti15': {'count': 1, 'last_timestamp': samples[0]['date']}}}).json()
    assert continued['rows'][0]['results']['uneti15']['count'] == 2


def test_invalid_sample_breaks_streak(client):
    samples = client.get('/api/scenarios/empty').json()['samples'][:4]
    samples[2]['Humidity'] = 101
    result = client.post('/api/predict-batch', json={'samples': samples, 'compare': True}).json()
    assert result['invalid_rows'] == 1
    assert 'Humidity' in result['rows'][2]['error']
    for mid in ('btc', 'uneti15'):
        assert result['rows'][3]['results'][mid]['count'] == 1
    samples[0]['date'] = 'NaT'
    assert client.post('/api/predict', json={'samples': samples[:1]}).status_code == 422


def test_timestamp_reset_and_gap_scenario(client):
    samples = client.get('/api/scenarios/gap').json()['samples']
    result = client.post('/api/predict-batch', json={'samples': samples}).json()
    assert result['rows'][3]['results']['uneti15']['count'] == 1
    assert result['rows'][3]['results']['uneti15']['reset_reason']
    samples[1]['date'] = samples[0]['date']
    result = client.post('/api/predict-batch', json={'samples': samples}).json()
    assert result['rows'][1]['results']['uneti15']['count'] == 1


def test_staging_scenarios_use_contiguous_training_rows(client):
    frame = pd.read_csv(ROOT / 'data/AI04/datatraining.txt')
    for name, label in [('occupied', 1), ('empty', 0)]:
        result = client.get(f'/api/scenarios/{name}')
        assert result.status_code == 200
        samples = result.json()['samples']
        assert len(samples) == 8
        start = int(np.flatnonzero(frame['date'].eq(samples[0]['date']).to_numpy())[0])
        original = frame.iloc[start:start + 8]
        assert original['Occupancy'].eq(label).all()
        assert original[FEATURES + ['date']].to_dict('records') == samples
        predicted = client.post('/api/predict-batch', json={'samples': samples, 'compare': True})
        assert predicted.status_code == 200
        assert set(predicted.json()['rows'][0]['results']) == {'btc', 'uneti15'}


def test_csv_upload_actual_uci_format(client):
    with open(ROOT / 'data/AI04/datatraining.txt', 'rb') as file:
        response = client.post('/api/upload', files={'file': ('sensors.txt', file, 'text/plain')}, data={'model_id': 'uneti15', 'compare': 'true'})
    assert response.status_code == 200
    result = response.json()
    assert len(result['rows']) == 8143
    assert not result['assumed_timestamps']
    assert result['invalid_rows'] == 0


def test_missing_timestamp_and_target_ignored(client, samples):
    frame = pd.DataFrame(samples).drop(columns='date')
    frame['Occupancy'] = 'THIS IS NOT AN INPUT'
    result = client.post('/api/upload', files={'file': ('demo.csv', frame.to_csv(index=False).encode())}).json()
    assert result['assumed_timestamps']
    assert not result['invalid_rows']
    assert 'Occupancy' not in result['rows'][0]['sensors']
    stamps = [pd.Timestamp(r['timestamp']) for r in result['rows']]
    assert (stamps[1] - stamps[0]).total_seconds() == 60


def test_reject_unknown_model_and_bad_data(client, samples):
    assert client.post('/api/predict', json={'model_id': '../random_forest', 'samples': samples[:1]}).status_code == 422
    samples[0]['Temperature'] = 'Infinity'
    assert client.post('/api/predict', json={'samples': samples[:1]}).status_code == 422
    assert client.post('/api/upload', files={'file': ('bad.csv', b'Temperature\n25')}).status_code == 422
    assert client.post('/api/upload', files={'file': ('bad.joblib', b'not a model')}).status_code == 422
    assert client.post('/api/predict-batch', json={'samples': []}).status_code == 422


def test_unavailable_model_does_not_fallback(client, samples):
    entry = registry['uneti15']
    original = entry['available']
    try:
        entry['available'] = False
        assert client.post('/api/predict', json={'samples': samples[:1]}).status_code == 503
        assert client.post('/api/predict', json={'model_id': 'btc', 'samples': samples[:1]}).status_code == 200
    finally:
        entry['available'] = original
