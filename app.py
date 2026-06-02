from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB = "vizyon_stok.db"


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS urunler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kod TEXT,
        ad TEXT,
        kategori TEXT,
        renk TEXT,
        fiyat REAL DEFAULT 0,
        stok INTEGER DEFAULT 0,
        kritik INTEGER DEFAULT 5
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS stok_hareketleri (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        urun_id INTEGER,
        tip TEXT,
        adet INTEGER,
        aciklama TEXT,
        tarih TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS satislar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        musteri TEXT,
        urun_id INTEGER,
        adet INTEGER,
        fiyat REAL,
        toplam REAL,
        tarih TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS uretim (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model TEXT,
        adet INTEGER,
        durum TEXT,
        tarih TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS sevkiyat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        musteri TEXT,
        telefon TEXT,
        adres TEXT,
        arac TEXT,
        sofor TEXT,
        durum TEXT,
        tarih TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS cariler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad TEXT,
        telefon TEXT,
        sehir TEXT,
        yetkili TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS cari_hareketleri (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cari_id INTEGER,
        tip TEXT,
        aciklama TEXT,
        tutar REAL,
        tarih TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


@app.route("/")
def index():
    conn = db()

    toplam_urun = conn.execute("SELECT COUNT(*) FROM urunler").fetchone()[0]
    toplam_stok = conn.execute("SELECT COALESCE(SUM(stok),0) FROM urunler").fetchone()[0]
    kritik_urun = conn.execute("SELECT COUNT(*) FROM urunler WHERE stok <= kritik").fetchone()[0]

    bugun = datetime.now().strftime("%Y-%m-%d")
    bugunku_satis = conn.execute(
        "SELECT COALESCE(SUM(toplam),0) FROM satislar WHERE tarih LIKE ?",
        (bugun + "%",)
    ).fetchone()[0]

    bekleyen_sevkiyat = conn.execute(
        "SELECT COUNT(*) FROM sevkiyat WHERE durum != 'Teslim Edildi'"
    ).fetchone()[0]

    toplam_borc = conn.execute(
        "SELECT COALESCE(SUM(tutar),0) FROM cari_hareketleri WHERE tip='Borç'"
    ).fetchone()[0]

    toplam_alacak = conn.execute(
        "SELECT COALESCE(SUM(tutar),0) FROM cari_hareketleri WHERE tip='Alacak'"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "index.html",
        toplam_urun=toplam_urun,
        toplam_stok=toplam_stok,
        kritik_urun=kritik_urun,
        bugunku_satis=bugunku_satis,
        bekleyen_sevkiyat=bekleyen_sevkiyat,
        toplam_borc=toplam_borc,
        toplam_alacak=toplam_alacak
    )


@app.route("/urunler", methods=["GET", "POST"])
def urunler():
    conn = db()

    if request.method == "POST":
        conn.execute("""
            INSERT INTO urunler (kod, ad, kategori, renk, fiyat, stok, kritik)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form.get("kod"),
            request.form.get("ad"),
            request.form.get("kategori"),
            request.form.get("renk"),
            request.form.get("fiyat", 0),
            request.form.get("stok", 0),
            request.form.get("kritik", 5)
        ))
        conn.commit()
        conn.close()
        return redirect("/urunler")

    urunler = conn.execute("SELECT * FROM urunler ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("urunler.html", urunler=urunler)


@app.route("/stok", methods=["GET", "POST"])
def stok():
    conn = db()

    if request.method == "POST":
        urun_id = request.form.get("urun_id")
        tip = request.form.get("tip")
        adet = int(request.form.get("adet", 0))
        aciklama = request.form.get("aciklama")
        tarih = datetime.now().strftime("%Y-%m-%d %H:%M")

        if tip == "Giriş":
            conn.execute("UPDATE urunler SET stok = stok + ? WHERE id=?", (adet, urun_id))
        else:
            conn.execute("UPDATE urunler SET stok = stok - ? WHERE id=?", (adet, urun_id))

        conn.execute("""
            INSERT INTO stok_hareketleri (urun_id, tip, adet, aciklama, tarih)
            VALUES (?, ?, ?, ?, ?)
        """, (urun_id, tip, adet, aciklama, tarih))

        conn.commit()
        conn.close()
        return redirect("/stok")

    urunler = conn.execute("SELECT * FROM urunler ORDER BY ad").fetchall()
    hareketler = conn.execute("""
        SELECT stok_hareketleri.*, urunler.ad AS urun_ad
        FROM stok_hareketleri
        LEFT JOIN urunler ON urunler.id = stok_hareketleri.urun_id
        ORDER BY stok_hareketleri.id DESC
    """).fetchall()

    conn.close()
    return render_template("stok.html", urunler=urunler, hareketler=hareketler)


@app.route("/satis", methods=["GET", "POST"])
def satis():
    conn = db()

    if request.method == "POST":
        musteri = request.form.get("musteri")
        urun_id = request.form.get("urun_id")
        adet = int(request.form.get("adet", 0))
        fiyat = float(request.form.get("fiyat", 0))
        toplam = adet * fiyat
        tarih = datetime.now().strftime("%Y-%m-%d %H:%M")

        conn.execute("""
            INSERT INTO satislar (musteri, urun_id, adet, fiyat, toplam, tarih)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (musteri, urun_id, adet, fiyat, toplam, tarih))

        conn.execute("UPDATE urunler SET stok = stok - ? WHERE id=?", (adet, urun_id))

        conn.commit()
        conn.close()
        return redirect("/satis")

    urunler = conn.execute("SELECT * FROM urunler ORDER BY ad").fetchall()
    satislar = conn.execute("""
        SELECT satislar.*, urunler.ad AS urun_ad
        FROM satislar
        LEFT JOIN urunler ON urunler.id = satislar.urun_id
        ORDER BY satislar.id DESC
    """).fetchall()

    conn.close()
    return render_template("satis.html", urunler=urunler, satislar=satislar)


@app.route("/uretim", methods=["GET", "POST"])
def uretim():
    conn = db()

    if request.method == "POST":
        conn.execute("""
            INSERT INTO uretim (model, adet, durum, tarih)
            VALUES (?, ?, ?, ?)
        """, (
            request.form.get("model"),
            request.form.get("adet"),
            request.form.get("durum"),
            request.form.get("tarih")
        ))
        conn.commit()
        conn.close()
        return redirect("/uretim")

    uretimler = conn.execute("SELECT * FROM uretim ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("uretim.html", uretimler=uretimler)


@app.route("/sevkiyat", methods=["GET", "POST"])
def sevkiyat():
    conn = db()

    if request.method == "POST":
        conn.execute("""
            INSERT INTO sevkiyat (musteri, telefon, adres, arac, sofor, durum, tarih)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            request.form.get("musteri"),
            request.form.get("telefon"),
            request.form.get("adres"),
            request.form.get("arac"),
            request.form.get("sofor"),
            request.form.get("durum"),
            request.form.get("tarih")
        ))
        conn.commit()
        conn.close()
        return redirect("/sevkiyat")

    sevkiyatlar = conn.execute("SELECT * FROM sevkiyat ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("sevkiyat.html", sevkiyatlar=sevkiyatlar)


@app.route("/cari", methods=["GET", "POST"])
def cari():
    conn = db()

    if request.method == "POST":
        islem = request.form.get("islem")

        if islem == "cari_ekle":
            conn.execute("""
                INSERT INTO cariler (ad, telefon, sehir, yetkili)
                VALUES (?, ?, ?, ?)
            """, (
                request.form.get("ad"),
                request.form.get("telefon"),
                request.form.get("sehir"),
                request.form.get("yetkili")
            ))

        elif islem == "hareket_ekle":
            conn.execute("""
                INSERT INTO cari_hareketleri (cari_id, tip, aciklama, tutar, tarih)
                VALUES (?, ?, ?, ?, ?)
            """, (
                request.form.get("cari_id"),
                request.form.get("tip"),
                request.form.get("aciklama"),
                request.form.get("tutar"),
                request.form.get("tarih")
            ))

        conn.commit()
        conn.close()
        return redirect("/cari")

    cariler = conn.execute("SELECT * FROM cariler ORDER BY id DESC").fetchall()

    hareketler = conn.execute("""
        SELECT cari_hareketleri.*, cariler.ad AS cari_ad
        FROM cari_hareketleri
        LEFT JOIN cariler ON cariler.id = cari_hareketleri.cari_id
        ORDER BY cari_hareketleri.id DESC
    """).fetchall()

    toplam_borc = conn.execute(
        "SELECT COALESCE(SUM(tutar),0) FROM cari_hareketleri WHERE tip='Borç'"
    ).fetchone()[0]

    toplam_alacak = conn.execute(
        "SELECT COALESCE(SUM(tutar),0) FROM cari_hareketleri WHERE tip='Alacak'"
    ).fetchone()[0]

    bakiye = toplam_borc - toplam_alacak

    conn.close()

    return render_template(
        "cari.html",
        cariler=cariler,
        hareketler=hareketler,
        toplam_borc=toplam_borc,
        toplam_alacak=toplam_alacak,
        bakiye=bakiye
    )


@app.route("/raporlar")
def raporlar():
    conn = db()

    toplam_satis = conn.execute("SELECT COALESCE(SUM(toplam),0) FROM satislar").fetchone()[0]
    toplam_urun = conn.execute("SELECT COUNT(*) FROM urunler").fetchone()[0]
    toplam_stok = conn.execute("SELECT COALESCE(SUM(stok),0) FROM urunler").fetchone()[0]
    kritik_urunler = conn.execute("SELECT * FROM urunler WHERE stok <= kritik").fetchall()

    son_satislar = conn.execute("""
        SELECT satislar.*, urunler.ad AS urun_ad
        FROM satislar
        LEFT JOIN urunler ON urunler.id = satislar.urun_id
        ORDER BY satislar.id DESC
        LIMIT 10
    """).fetchall()

    conn.close()

    return render_template(
        "raporlar.html",
        toplam_satis=toplam_satis,
        toplam_urun=toplam_urun,
        toplam_stok=toplam_stok,
        kritik_urunler=kritik_urunler,
        son_satislar=son_satislar
    )


@app.route("/urun-sil/<int:id>")
def urun_sil(id):
    conn = db()
    conn.execute("DELETE FROM urunler WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/urunler")


if __name__ == "__main__":
    app.run(debug=True)
