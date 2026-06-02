from flask import Flask, render_template, request, redirect, session, Response
from functools import wraps
import sqlite3
from datetime import datetime
import csv
import io

app = Flask(__name__)
app.secret_key = "vizyonstokgizlisifre"
DB = "vizyon_stok.db"


def db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS urunler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kod TEXT,
        ad TEXT,
        kategori TEXT,
        renk TEXT,
        fiyat REAL DEFAULT 0,
        stok INTEGER DEFAULT 0,
        kritik INTEGER DEFAULT 5
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS stok_hareketleri (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        urun_id INTEGER,
        tip TEXT,
        adet INTEGER,
        aciklama TEXT,
        tarih TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS satislar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        musteri TEXT,
        urun_id INTEGER,
        adet INTEGER,
        fiyat REAL,
        toplam REAL,
        tarih TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS uretim (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model TEXT,
        adet INTEGER,
        durum TEXT,
        tarih TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS sevkiyat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        musteri TEXT,
        telefon TEXT,
        adres TEXT,
        arac TEXT,
        sofor TEXT,
        durum TEXT,
        tarih TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS cariler (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ad TEXT,
        telefon TEXT,
        sehir TEXT,
        yetkili TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS cari_hareketleri (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cari_id INTEGER,
        tip TEXT,
        aciklama TEXT,
        tutar REAL,
        tarih TEXT
    )""")

    conn.commit()
    conn.close()


init_db()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


@app.route("/login", methods=["GET", "POST"])
def login():
    hata = None

    if request.method == "POST":
        kullanici = request.form.get("kullanici")
        sifre = request.form.get("sifre")

        if kullanici == "admin" and sifre == "1234":
            session["user"] = kullanici
            return redirect("/")
        else:
            hata = "Kullanıcı adı veya şifre hatalı"

    return render_template("login.html", hata=hata)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/")
@login_required
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
@login_required
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


@app.route("/urun-sil/<int:id>")
@login_required
def urun_sil(id):
    conn = db()
    conn.execute("DELETE FROM urunler WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect("/urunler")


@app.route("/stok", methods=["GET", "POST"])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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


@app.route("/excel/urunler")
@login_required
def excel_urunler():
    conn = db()
    urunler = conn.execute("SELECT * FROM urunler").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Kod", "Ürün Adı", "Kategori", "Renk", "Fiyat", "Stok", "Kritik"])

    for u in urunler:
        writer.writerow([u["kod"], u["ad"], u["kategori"], u["renk"], u["fiyat"], u["stok"], u["kritik"]])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=urunler.csv"}
    )


@app.route("/excel/satislar")
@login_required
def excel_satislar():
    conn = db()

    satislar = conn.execute("""
        SELECT satislar.*, urunler.ad AS urun_ad
        FROM satislar
        LEFT JOIN urunler ON urunler.id = satislar.urun_id
        ORDER BY satislar.id DESC
    """).fetchall()

    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Tarih", "Müşteri", "Ürün", "Adet", "Birim Fiyat", "Toplam"])

    for s in satislar:
        writer.writerow([s["tarih"], s["musteri"], s["urun_ad"], s["adet"], s["fiyat"], s["toplam"]])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=satislar.csv"}
    )


@app.route("/excel/cariler")
@login_required
def excel_cariler():
    conn = db()
    cariler = conn.execute("SELECT * FROM cariler").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Cari Adı", "Telefon", "Şehir", "Yetkili"])

    for c in cariler:
        writer.writerow([c["ad"], c["telefon"], c["sehir"], c["yetkili"]])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=cariler.csv"}
    )


if __name__ == "__main__":
    app.run(debug=True)
