"""Content-addressed raw HTTP receipts; source/evidence identity is never cached."""
import base64
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import time
from uuid import uuid4

from filelock import FileLock, Timeout


class OCRResponseCache:
    def __init__(self, directory, ttl=86400):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.ttl = int(ttl)
        if self.ttl <= 0:
            raise ValueError('OCR缓存TTL必须为正数')

    @staticmethod
    def key(content_sha256, endpoint, service_version='orderChange-v1'):
        # Signed URLs, upload IDs, prompts and parsers do not change the OCR input.
        request = dict(content_sha256=content_sha256, endpoint=endpoint,
            task='orderChange', callBack='', taskType='', service_version=service_version)
        return sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()

    @contextmanager
    def singleflight(self, key, guard=None):
        lock = FileLock(self.directory / (key + '.lock'))
        started = time.monotonic()
        while True:
            if guard:
                guard()
            try:
                lock.acquire(timeout=0.25)
                break
            except Timeout:
                if time.monotonic() - started > 660:
                    raise TimeoutError('相同文件的OCR仍在执行，请稍后查看其结果')
        try:
            yield
        finally:
            lock.release()

    def read(self, key):
        try:
            entry = json.loads((self.directory / (key + '.json')).read_text(encoding='utf-8'))
            wire = base64.b64decode(entry['wire'], validate=True)
            if entry['key'] != key or time.time() >= min(entry['expires_at'], entry['created_at'] + self.ttl) or sha256(wire).hexdigest() != entry['sha256']:
                return None
            json.loads(wire)
            return wire, entry['created_at']
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def write(self, key, wire):
        now = time.time()
        entry = dict(key=key, created_at=now, expires_at=now + self.ttl,
            sha256=sha256(wire).hexdigest(), wire=base64.b64encode(wire).decode('ascii'))
        target = self.directory / (key + '.json')
        temporary = target.with_suffix('.' + uuid4().hex + '.tmp')
        try:
            temporary.write_text(json.dumps(entry), encoding='utf-8')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        return now
