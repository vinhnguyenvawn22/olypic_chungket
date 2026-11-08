"""Serve the bundle's locked temporal Logistic without training or reselection."""

import hashlib
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


HISTORY_SIZE = 9  # CO2_slope10 needs the current sample and nine preceding samples.


class BundleRuntime:
    def __init__(self, path: Path):
        root = path.parent.parent
        bundle = joblib.load(path)
        self.lock = bundle['lock']
        source = root / 'src/improvement.py'
        if hashlib.sha256(source.read_bytes()).hexdigest() != self.lock['source_sha256']:
            raise ValueError('Ma tao dac trung khac phien ban da huan luyen.')
        if self.lock['model'] != 'temporal' or self.lock['action']['policy'] != 'three':
            raise ValueError('Demo nay chi ho tro cau hinh temporal + three da khoa.')
        self.fitted = bundle['models'][self.lock['model']]
        if self.fitted.mode != 'temporal':
            raise ValueError('Bundle khong co bo tao dac trung temporal tuong thich.')
        self.classification_threshold = float(self.lock['threshold'])
        if not 0 < self.classification_threshold < 1:
            raise ValueError('Nguong phan loai khong hop le.')
        self.parameters = {
            'selected_model': self.lock['model'],
            'classification_threshold': self.classification_threshold,
            'history_samples': HISTORY_SIZE,
            'logisticregression__C': self.fitted.estimator.named_steps['logisticregression'].C,
        }

    def predict_rows(self, rows, history):
        """Score contiguous valid segments; keep causal history local to this request."""
        predictions = {}
        pending = []
        history = list(history[-HISTORY_SIZE:])

        def flush():
            nonlocal history
            if not pending:
                return
            records = history + [record for _, record in pending]
            frame = pd.DataFrame(records)
            frame['date'] = pd.to_datetime(frame['date'], utc=True).dt.tz_localize(None)
            scores = self.fitted.score(frame)[-len(pending):]
            if not np.isfinite(scores).all() or ((scores < 0) | (scores > 1)).any():
                raise ValueError('Bundle tra ve xac suat khong hop le.')
            predictions.update((index, (int(p >= self.classification_threshold), float(p)))
                               for (index, _), p in zip(pending, scores))
            seconds = frame['date'].diff().dt.total_seconds()
            breaks = np.flatnonzero(~((seconds > 0) & (seconds <= 120)).to_numpy())
            history = records[int(breaks[-1]):][-HISTORY_SIZE:]
            pending.clear()

        for index, row in enumerate(rows):
            if row['error']:
                flush()
                history = []
            else:
                pending.append((index, {**row['sensors'], 'date': row['timestamp']}))
        flush()
        return predictions, history
