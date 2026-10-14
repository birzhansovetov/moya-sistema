"""Bounded parsing and private S3 storage for user-supplied books."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
import os
import posixpath
import zipfile

import boto3
from botocore.config import Config
from defusedxml import ElementTree as ET
from pypdf import PdfReader


MAX_BOOK_BYTES = 15 * 1024 * 1024
MAX_EXPANDED_BYTES = 50 * 1024 * 1024
MIME = {'epub': 'application/epub+zip', 'fb2': 'application/xml', 'pdf': 'application/pdf'}


class InvalidBook(ValueError):
    pass


@dataclass
class InspectedBook:
    format: str
    title: str
    chapters: list[dict]
    paragraphs: list[str]
    page_count: int | None = None


def _text(node) -> str:
    return ' '.join(''.join(node.itertext()).split())


def _local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def _safe_zip_name(name: str) -> bool:
    return bool(name) and not name.startswith('/') and '..' not in PurePosixPath(name).parts and '\\' not in name


def _epub(data: bytes) -> InspectedBook:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 500 or any(not _safe_zip_name(entry.filename) for entry in entries):
                raise InvalidBook('Небезопасная структура EPUB')
            if sum(entry.file_size for entry in entries) > MAX_EXPANDED_BYTES or any(entry.file_size > max(100_000, entry.compress_size * 200) for entry in entries):
                raise InvalidBook('EPUB слишком велик после распаковки')
            if archive.read('mimetype').strip() != b'application/epub+zip':
                raise InvalidBook('Файл не является EPUB')
            container = ET.fromstring(archive.read('META-INF/container.xml'))
            rootfile = next((node.attrib.get('full-path') for node in container.iter() if _local(node.tag) == 'rootfile'), None)
            if not rootfile or not _safe_zip_name(rootfile):
                raise InvalidBook('В EPUB нет описания книги')
            package = ET.fromstring(archive.read(rootfile))
            manifest = {node.attrib.get('id'): node.attrib.get('href') for node in package.iter() if _local(node.tag) == 'item'}
            spine = [node.attrib.get('idref') for node in package.iter() if _local(node.tag) == 'itemref']
            title = next((_text(node) for node in package.iter() if _local(node.tag) == 'title' and _text(node)), '')
            paragraphs, chapters = [], []
            for index, item_id in enumerate(spine):
                href = manifest.get(item_id)
                if not href or not _safe_zip_name(href):
                    continue
                path = posixpath.normpath(posixpath.join(posixpath.dirname(rootfile), href.split('#')[0]))
                if not _safe_zip_name(path):
                    raise InvalidBook('Небезопасный путь внутри EPUB')
                root = ET.fromstring(archive.read(path))
                chapter_text = [_text(node) for node in root.iter() if _local(node.tag) == 'p']
                chapter_text = [text for text in chapter_text if text]
                if chapter_text:
                    chapters.append({'title': f'Глава {index + 1}', 'offset': len(paragraphs)})
                    paragraphs.extend(chapter_text)
            if not paragraphs:
                raise InvalidBook('В EPUB нет доступного текста')
            return InspectedBook('epub', title, chapters, paragraphs)
    except (zipfile.BadZipFile, KeyError, ET.ParseError, OSError, RuntimeError) as exc:
        raise InvalidBook('EPUB повреждён или не поддерживается') from exc


def _fb2(data: bytes) -> InspectedBook:
    try:
        root = ET.fromstring(data)
    except (ET.ParseError, ValueError) as exc:
        raise InvalidBook('FB2 повреждён') from exc
    if _local(root.tag) != 'FictionBook':
        raise InvalidBook('Файл не является FB2')
    title = next((_text(node) for node in root.iter() if _local(node.tag) == 'book-title' and _text(node)), '')
    paragraphs, chapters = [], []
    for section in (node for node in root.iter() if _local(node.tag) == 'section'):
        direct = [node for node in section if _local(node.tag) == 'p']
        words = [_text(node) for node in direct if _text(node)]
        if words:
            chapters.append({'title': f'Глава {len(chapters) + 1}', 'offset': len(paragraphs)})
            paragraphs.extend(words)
    if not paragraphs:
        raise InvalidBook('В FB2 нет доступного текста')
    return InspectedBook('fb2', title, chapters, paragraphs)


def _pdf(data: bytes) -> InspectedBook:
    if not data.startswith(b'%PDF-'):
        raise InvalidBook('Файл не является PDF')
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted or not reader.pages:
            raise InvalidBook('PDF защищён паролем или пуст')
        count = len(reader.pages)
        title = str(reader.metadata.title or '') if reader.metadata else ''
        return InspectedBook('pdf', title, [], [], count)
    except InvalidBook:
        raise
    except Exception as exc:
        raise InvalidBook('PDF повреждён или не поддерживается') from exc


def inspect_book(filename: str, data: bytes) -> InspectedBook:
    if not data or len(data) > MAX_BOOK_BYTES:
        raise InvalidBook('Файл пуст или превышает 15 МБ')
    ext = filename.lower().rsplit('.', 1)[-1]
    if ext not in MIME:
        raise InvalidBook('Поддерживаются только EPUB, FB2 и PDF')
    return {'epub': _epub, 'fb2': _fb2, 'pdf': _pdf}[ext](data)


class S3BookStore:
    def __init__(self, client, bucket: str):
        self.client, self.bucket = client, bucket

    @classmethod
    def from_env(cls):
        names = ('AWS_ENDPOINT_URL_S3', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'BOOK_STORAGE_BUCKET')
        values = [os.getenv(name, '') for name in names]
        if not all(values):
            return None
        endpoint, access, secret, bucket = values
        if not endpoint.startswith('https://'):
            raise ValueError('Book storage endpoint must use HTTPS')
        client = boto3.client('s3', endpoint_url=endpoint, aws_access_key_id=access,
                              aws_secret_access_key=secret, region_name=os.getenv('AWS_REGION', 'us-east-2'),
                              config=Config(s3={'addressing_style': 'path'}))
        return cls(client, bucket)

    def put(self, key: str, data: bytes, content_type: str):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)['Body'].read(MAX_BOOK_BYTES + 1)

    def delete(self, key: str):
        self.client.delete_object(Bucket=self.bucket, Key=key)
