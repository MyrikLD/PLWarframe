import hashlib
import logging
import lzma
import os
import re
from threading import Event
from typing import Iterable

import requests

log = logging.getLogger('Models')

session = requests.Session()


def get_lzma(url, kill_event: Event, callback=None):
    log = logging.getLogger('LZMA')

    resp = session.get(url, stream=True, timeout=30)
    size = int(resp.headers['content-length'])
    data = b''

    log.info(f'Start loading: {url}')

    for chunk in resp.iter_content(4096):
        if kill_event.is_set():
            raise Exception('Kill event')

        data += chunk

        if callback:
            callback(size, len(data))

    if callback:
        callback(size, len(data))

    return lzma.decompress(data)


def md5(fname: str, kill_event: Event):
    hash_md5 = hashlib.md5()

    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            if kill_event.is_set():
                raise Exception('Kill event')
            hash_md5.update(chunk)
    return hash_md5.hexdigest().upper()


class Line:
    prefix = ''

    def __init__(self, data):
        try:
            data = re.findall(r'(.*?).([A-Z0-9]*).lzma,(\d+)', data)[0]
        except:
            raise Exception(data)
        path, md5, size = data
        self.path = path
        self.md5 = md5
        self.size = int(size)

    def check(self, kill_event: Event):
        if not os.path.isfile(self.full_path):
            return False
        real_md5 = md5(self.full_path, kill_event=kill_event)
        return self.md5 == real_md5

    @property
    def full_path(self):
        return self.prefix + self.path

    @property
    def url(self):
        return self.full_path + '.' + self.md5 + '.lzma'

    def download(self, kill_event: Event, callback=None):
        return get_lzma(self.url, kill_event=kill_event, callback=callback)

    def __str__(self):
        return f'{self.path}.{self.md5}.lzma,{self.size}'

    def __hash__(self):
        return hash(str(self))


class FileList(set):
    log = logging.getLogger('Models')
    _prefix = ''

    def __init__(self, items: Iterable[Line] = ()):
        if type(items) is FileList:
            self._prefix = items.prefix
            self.log = items.log

        for item in items:
            self.add(item)

    def add(self, item: Line):
        item.locality = self.prefix
        return super().add(item)

    @property
    def prefix(self):
        return self._prefix

    @prefix.setter
    def prefix(self, prefix):
        self._prefix = prefix
        for i in self:
            i.prefix = self._prefix

    @classmethod
    def from_file(cls, path):
        obj = cls()

        with open(path, 'r') as f:
            lines = f.read().splitlines()
            for i in lines:
                if i:
                    obj.add(Line(i))

        return obj

    @classmethod
    def from_lzma(cls, path):
        obj = cls()

        with open(path, 'rb') as f:
            lines = lzma.decompress(f.read()).decode().splitlines()
            for i in lines:
                if i:
                    obj.add(Line(i))

        return obj

    def to_file(self, path):
        with open(path, 'w') as f:
            text = '\r\n'.join(
                sorted([str(i) for i in self])
            ) + '\r\n'

            f.write(text)
        self.log.info(f'Saved to: {path}')

    @classmethod
    def from_url(cls, path, kill_event: Event):
        text = get_lzma(path, kill_event=kill_event)
        lines = text.decode().split('\r\n')
        obj = cls()
        for i in lines:
            if i:
                obj.add(Line(i))
        return obj

    def get(self, path: str):
        for i in self:
            if i.path == path:
                return i

    def __str__(self):
        return '\n'.join([str(i) for i in self])

    @property
    def size(self):
        return sum(i.size for i in self)

    def exclude(self, path) -> 'FileList':
        fl = FileList([i for i in self if not i.path.startswith(path)])
        fl.prefix = self.prefix
        return fl
