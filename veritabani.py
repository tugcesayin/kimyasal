"""
Kullanıcı, favori ve blog verileri için ortak veritabanı katmanı.

- DATABASE_URL ortam değişkeni bir PostgreSQL adresiyse (Render'da olduğu gibi)
  veriler kalıcı olarak PostgreSQL'de tutulur.
- Değilse (kendi bilgisayarında) proje klasöründeki kullanici.db (SQLite) kullanılır.

Sorgular SQLite tarzı "?" yer tutucularıyla yazılır; PostgreSQL için otomatik çevrilir.
"""
import os
import sqlite3
from contextlib import closing
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_YOLU = os.path.join(BASE_DIR, "kullanici.db")

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))

if POSTGRES:
    import psycopg
    from psycopg.rows import dict_row
    BUTUNLUK_HATASI = psycopg.IntegrityError
    ID_SUTUNU = "SERIAL PRIMARY KEY"
else:
    BUTUNLUK_HATASI = sqlite3.IntegrityError
    ID_SUTUNU = "INTEGER PRIMARY KEY AUTOINCREMENT"


def baglan():
    if POSTGRES:
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    conn = sqlite3.connect(SQLITE_YOLU)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def calistir(sql, parametreler=(), tek=False, hepsi=False):
    """Bir sorgu çalıştırır ve kaydeder. tek=True ilk satırı, hepsi=True tüm satırları döndürür."""
    if POSTGRES:
        sql = sql.replace("?", "%s")
    with closing(baglan()) as conn:
        cur = conn.execute(sql, parametreler)
        sonuc = cur.fetchone() if tek else cur.fetchall() if hepsi else None
        conn.commit()
    if tek:
        return dict(sonuc) if sonuc else None
    if hepsi:
        return [dict(s) for s in sonuc]
    return None


def simdi():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


VARSAYILAN_YAZILAR = [
    (
        "Altın ve Aqua Regia: Kral Suyu Gerçeği",
        "Kimyasal Reaksiyonlar",
        "Aqua regia (Kral Suyu), derişik hidroklorik asit ve derişik nitrik asidin genellikle 3:1 hacim "
        "oranında karıştırılmasıyla oluşan oldukça aşındırıcı bir çözeltidir.\n\nAltın ve platin gibi soy "
        "metalleri çözebilme kapasitesine sahip az sayıdaki karışımdan biridir. Reaksiyon esnasında açığa "
        "çıkan serbest klor ve nitrozil klorür (NOCl), altını kloroaurik asit formunda çözeltiye geçirir. "
        "Bu çözeltiyle çalışırken çeker ocak kullanılması hayati önem taşır.",
        "2026-09-09 12:00:00",
    ),
    (
        "Laboratuvarda Asit Seyreltme: Asidi Suya Ekle!",
        "Laboratuvar Güvenliği",
        "Kimya laboratuvarlarının altın kuralı: 'Daima asidi suya ekleyin, asla suyu aside eklemeyin.'\n\n"
        "Sülfürik asit gibi güçlü asitlerin su ile hidrasyon reaksiyonu aşırı ekzotermiktir (yüksek ısı "
        "açığa çıkar). Eğer su derişik asidin üzerine dökülürse, az miktardaki su anında kaynama noktasına "
        "ulaşarak buharlaşır ve etrafa asit sıçramasına yol açar. Su kabına yavaşça ve karıştırılarak "
        "eklenen asit ise açığa çıkan ısının su tarafından güvenle emilmesini sağlar.",
        "2026-09-08 12:00:00",
    ),
]


def tablolari_olustur():
    calistir(f"""
        CREATE TABLE IF NOT EXISTS kullanicilar (
            id {ID_SUTUNU},
            isim TEXT NOT NULL,
            soyisim TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            sifre TEXT NOT NULL
        )
    """)
    calistir(f"""
        CREATE TABLE IF NOT EXISTS favoriler (
            id {ID_SUTUNU},
            kullanici_id INTEGER NOT NULL REFERENCES kullanicilar(id) ON DELETE CASCADE,
            isim TEXT NOT NULL,
            formul TEXT,
            cid INTEGER,
            eklenme TEXT NOT NULL,
            UNIQUE (kullanici_id, isim)
        )
    """)
    calistir(f"""
        CREATE TABLE IF NOT EXISTS blog_yazilari (
            id {ID_SUTUNU},
            kullanici_id INTEGER REFERENCES kullanicilar(id) ON DELETE SET NULL,
            yazar TEXT NOT NULL,
            baslik TEXT NOT NULL,
            etiket TEXT NOT NULL,
            icerik TEXT NOT NULL,
            tarih TEXT NOT NULL
        )
    """)
    # Blog boşsa örnek yazıları ekle
    if not calistir("SELECT id FROM blog_yazilari LIMIT 1", tek=True):
        for baslik, etiket, icerik, tarih in VARSAYILAN_YAZILAR:
            calistir(
                "INSERT INTO blog_yazilari (kullanici_id, yazar, baslik, etiket, icerik, tarih) VALUES (NULL, ?, ?, ?, ?, ?)",
                ("kimyasAl Ekibi", baslik, etiket, icerik, tarih),
            )
