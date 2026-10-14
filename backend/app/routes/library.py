import json
import zipfile
import xml.etree.ElementTree as ET
from functools import lru_cache
from importlib.resources import files
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from app.auth import get_current_user
from app.content_review import is_revoked
from app.db import get_db
from app.models import User
from sqlalchemy.orm import Session
router=APIRouter(prefix='/api/library',tags=['library'])
LOCAL_BOOKS = {
    'chekhov-chameleon': 'chekhov-chameleon.epub',
    'tolstoy-after-ball': 'tolstoy-after-ball.epub',
    'turgenev-mumu': 'turgenev-mumu.epub',
    'grin-scarlet-sails': 'grin-scarlet-sails.epub',
    'chekhov-cherry-orchard-mybook': 'chekhov-cherry-orchard-mybook.epub',
    'pushkin-captains-daughter': 'pushkin-captains-daughter.epub',
    'turgenev-hunters-notes': 'turgenev-hunters-notes.epub',
    'turgenev-bezhin-meadow': 'turgenev-bezhin-meadow.epub',
    'gorky-old-izergil': 'gorky-old-izergil.epub',
    'chekhov-lady-dog': 'chekhov-lady-dog.epub',
    'pushkin-queen-spades': 'pushkin-queen-spades.epub',
    'chekhov-new-villa': 'chekhov-new-villa.epub',
}


def local_book(book_id: str):
    name = LOCAL_BOOKS.get(book_id)
    if not name:
        raise HTTPException(404, 'Для этой книги пока нет файла для скачивания')
    return files('app.content').joinpath('ebooks', name)


@router.get('/guides')
def guides(area:Literal['personal','reading','finance','sport'],user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    items=json.loads(files('app.content').joinpath('guides.json').read_text())
    return {'items':[item for item in items if item['area']==area and not is_revoked(db,'guide',item['id'],str(item.get('version','v1')))]}


@router.get('/books')
def books(user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    items=json.loads(files('app.content').joinpath('book_suggestions.json').read_text())
    return {'items':[item | {'available_offline':item['id'] in LOCAL_BOOKS} for item in items if not is_revoked(db,'book',item['id'],str(item.get('version','v1')))]}


@router.get('/books/{book_id}/download')
def download_book(book_id:str,user:User=Depends(get_current_user)):
    book=local_book(book_id)
    return FileResponse(book,media_type='application/epub+zip',filename=book.name)


@lru_cache(maxsize=8)
def book_paragraphs(book_id:str):
    book=local_book(book_id)
    with zipfile.ZipFile(book) as archive:
        chapters=sorted((name for name in archive.namelist() if name.startswith('OPS/c') and name.endswith('.xhtml')),
                        key=lambda name:int(name.split('/')[-1].split('_')[0][1:]))
        if not chapters:
            raise HTTPException(500,'Текст книги недоступен')
        paragraphs=[]
        for chapter in chapters:
            root=ET.fromstring(archive.read(chapter))
            paragraphs.extend(' '.join(''.join(node.itertext()).split()) for node in root.iter('{http://www.w3.org/1999/xhtml}p'))
    return [paragraph for paragraph in paragraphs if paragraph]


@router.get('/books/{book_id}/read')
def read_book(book_id:str,offset:int=Query(default=0,ge=0),user:User=Depends(get_current_user)):
    paragraphs=book_paragraphs(book_id)
    end=min(offset+60,len(paragraphs))
    return {'paragraphs':paragraphs[offset:end], 'total':len(paragraphs), 'next_offset':end if end<len(paragraphs) else None}
