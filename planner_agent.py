"""
SANAL PLANNER - POC v1.0
EVE Kozmetik için Agentic Retail Planning Assistant

Bu script:
1. Trading raporunu okur (kategori bazlı)
2. Ürün raporunu okur (SKU bazlı)
3. Yukarıdan aşağıya analiz yapar
4. Sevkiyat ve indirim önerileri üretir
"""

import pandas as pd
import numpy as np
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

# =============================================================================
# KURALLAR (Hibrit Sistem - Temel Kurallar)
# =============================================================================

KURALLAR = {
    # Kural 1: Bütçe sapması
    "butce_sapma_kritik": 0.30,  # %30 ve üzeri sapma kritik
    
    # Kural 2: Cover hedefleri
    "cover_depo_hedef": 12,      # Depo dahil 12 hafta
    "cover_magaza_min": 8,       # Mağaza min 8 hafta
    "cover_magaza_max": 12,      # Mağaza max 12 hafta
    
    # Kural 3: İndirim başarı kriteri (elastikiyete göre dinamik)
    "indirim_basari_orani": 0.5, # Beklentinin en az %50'si
    
    # Kural 4: Stok devir
    "stok_devir_hedef_hafta": 12,
    
    # Kural 5: Yok satış
    "top_sku_sayisi": 100,       # Top 100 SKU'da tolerans yok
    "yok_satis_kritik_oran": 0.30,  # Diğerlerinde %30 üzeri kritik
}

# =============================================================================
# VERİ OKUMA
# =============================================================================

def veri_yukle(trading_path: str, urun_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Excel dosyalarını yükle"""
    trading = pd.read_excel(trading_path, sheet_name='mtd')
    urun = pd.read_excel(urun_path)
    return trading, urun

# =============================================================================
# ANALİZ MODÜLÜ
# =============================================================================

@dataclass
class KategoriBulgu:
    kategori: str
    butce_sapma: float
    lfl_degisim: float
    cover: float
    margin: float
    sorun_var: bool
    sorun_detay: List[str]

@dataclass
class SKUBulgu:
    sku_kod: str
    sku_adi: str
    kategori: str
    depo_stok: int
    magaza_stok: int
    haftalik_satis: float
    cover_hafta: float
    indirim_orani: float
    aksiyon: str  # "SEVK", "INDIRIM", "IZLE", "OK"
    oncelik: int  # 1=Kritik, 2=Yüksek, 3=Normal

def kategori_analiz(trading: pd.DataFrame) -> List[KategoriBulgu]:
    """Kategori bazlı analiz - sorunlu kategorileri bul"""
    bulgular = []
    
    for _, row in trading.iterrows():
        kategori = row['Satır Etiketleri']
        if pd.isna(kategori) or 'Total' in str(kategori):
            continue
            
        # Bütçe sapması (negatif = hedefin altında)
        butce_sapma = row.get('Achieved TY Sales Budget Value TRY', 0)
        if pd.isna(butce_sapma):
            butce_sapma = 0
            
        # LFL değişim
        lfl_degisim = row.get('LFL Sales Value TYvsLY LC%', 0)
        if pd.isna(lfl_degisim):
            lfl_degisim = 0
            
        # Cover
        cover = row.get('TY Store Back Cover', 0)
        if pd.isna(cover):
            cover = 0
            
        # Margin
        margin = row.get('TY Gross Margin TRY', 0)
        if pd.isna(margin):
            margin = 0
        
        # Sorun tespiti
        sorunlar = []
        sorun_var = False
        
        # Kural 1: Bütçe sapması kontrolü
        if abs(butce_sapma) >= KURALLAR["butce_sapma_kritik"]:
            sorun_var = True
            if butce_sapma < 0:
                sorunlar.append(f"❌ Bütçe altında: {butce_sapma*100:.1f}%")
            else:
                sorunlar.append(f"⚠️ Bütçe aşımı: +{butce_sapma*100:.1f}%")
        
        # LFL negatif
        if lfl_degisim < -0.10:  # %10'dan fazla küçülme
            sorun_var = True
            sorunlar.append(f"📉 LFL küçülme: {lfl_degisim*100:.1f}%")
        
        # Cover yüksek (fazla stok)
        if cover > KURALLAR["cover_depo_hedef"]:
            sorun_var = True
            sorunlar.append(f"📦 Cover yüksek: {cover:.1f} hafta")
        
        # Negatif margin
        if margin < 0:
            sorun_var = True
            sorunlar.append(f"💰 Negatif margin: {margin*100:.1f}%")
        
        bulgular.append(KategoriBulgu(
            kategori=kategori,
            butce_sapma=butce_sapma,
            lfl_degisim=lfl_degisim,
            cover=cover,
            margin=margin,
            sorun_var=sorun_var,
            sorun_detay=sorunlar
        ))
    
    return bulgular

def sku_analiz(urun: pd.DataFrame, sorunlu_kategoriler: List[str]) -> List[SKUBulgu]:
    """SKU bazlı analiz - aksiyon gereken ürünleri bul"""
    bulgular = []
    
    # Haftalık satışa göre sırala (top SKU tespiti için)
    urun['toplam_satis'] = urun['TW Adet'].fillna(0) + urun['LW Adet'].fillna(0)
    urun_sirali = urun.sort_values('toplam_satis', ascending=False)
    top_sku_listesi = urun_sirali.head(KURALLAR["top_sku_sayisi"])['Ürün Kodu'].tolist()
    
    for _, row in urun.iterrows():
        sku_kod = row['Ürün Kodu']
        sku_adi = row['Ürün ']
        kategori = row['Kategori ']
        
        depo_stok = row.get('Anlık Depo Stok Adet', 0) or 0
        magaza_stok = row.get('Anlık Mğz Stok Adet', 0) or 0
        toplam_stok = depo_stok + magaza_stok
        
        tw_satis = row.get('TW Adet', 0) or 0
        lw_satis = row.get('LW Adet', 0) or 0
        haftalik_satis = (tw_satis + lw_satis) / 2  # Ortalama
        
        indirim_orani = row.get('TW İO', 0) or 0
        
        # Cover hesapla
        if haftalik_satis > 0:
            cover_hafta = toplam_stok / haftalik_satis
        else:
            cover_hafta = 999  # Satış yok, stok var = sonsuz cover
        
        # Aksiyon belirleme
        aksiyon = "OK"
        oncelik = 3
        
        # Mağaza cover hesapla (mağaza stok / haftalık satış)
        if haftalik_satis > 0:
            magaza_cover = magaza_stok / haftalik_satis
        else:
            magaza_cover = 999
        
        # SEVK gerekli: Depoda var, mağazada cover düşük, satış var
        # Mağaza cover 4 haftanın altındaysa ve depoda stok varsa sevk et
        if depo_stok > 100 and magaza_cover < 4 and haftalik_satis > 20:
            aksiyon = "SEVK"
            oncelik = 1 if sku_kod in top_sku_listesi else 2
        
        # SEVK - Orta öncelik: Depoda fazla stok var, mağazada makul
        elif depo_stok > 500 and magaza_cover < 8 and haftalik_satis > 10:
            aksiyon = "SEVK"
            oncelik = 2
        
        # İNDİRİM gerekli: Cover çok yüksek (>20 hafta), satış düşük
        elif cover_hafta > 20 and haftalik_satis < 30:
            aksiyon = "INDIRIM"
            oncelik = 2
        
        # İNDİRİM - Yüksek cover genel
        elif cover_hafta > KURALLAR["cover_depo_hedef"] * 2 and haftalik_satis < 50:
            aksiyon = "INDIRIM"
            oncelik = 3
        
        # İZLE: Potansiyel sorun var
        elif cover_hafta > KURALLAR["cover_magaza_max"]:
            aksiyon = "IZLE"
            oncelik = 3
        
        # Sadece sorunlu kategorilerdeki veya aksiyon gereken SKU'ları ekle
        if aksiyon != "OK" or kategori in sorunlu_kategoriler:
            bulgular.append(SKUBulgu(
                sku_kod=sku_kod,
                sku_adi=sku_adi if pd.notna(sku_adi) else str(sku_kod),
                kategori=kategori,
                depo_stok=int(depo_stok),
                magaza_stok=int(magaza_stok),
                haftalik_satis=haftalik_satis,
                cover_hafta=cover_hafta,
                indirim_orani=indirim_orani,
                aksiyon=aksiyon,
                oncelik=oncelik
            ))
    
    # Önceliğe göre sırala
    bulgular.sort(key=lambda x: (x.oncelik, -x.haftalik_satis))
    
    return bulgular

# =============================================================================
# RAPOR ÜRETME
# =============================================================================

def rapor_uret(kategori_bulgular: List[KategoriBulgu], 
               sku_bulgular: List[SKUBulgu]) -> str:
    """Agent çıktısını üret"""
    
    rapor = []
    rapor.append("=" * 70)
    rapor.append("📊 SANAL PLANNER - HAFTALIK ANALİZ RAPORU")
    rapor.append(f"📅 Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    rapor.append("=" * 70)
    
    # BÖLÜM 1: KATEGORİ ANALİZİ
    rapor.append("\n" + "─" * 70)
    rapor.append("📈 BÖLÜM 1: KATEGORİ BAZLI ANALİZ")
    rapor.append("─" * 70)
    
    sorunlu_kategoriler = [b for b in kategori_bulgular if b.sorun_var]
    
    if sorunlu_kategoriler:
        rapor.append(f"\n🔴 {len(sorunlu_kategoriler)} KATEGORİDE SORUN TESPİT EDİLDİ:\n")
        
        for bulgu in sorunlu_kategoriler:
            rapor.append(f"▶ {bulgu.kategori}")
            rapor.append(f"  Bütçe Sapma: {bulgu.butce_sapma*100:.1f}% | LFL: {bulgu.lfl_degisim*100:.1f}% | Cover: {bulgu.cover:.1f} hf | Margin: {bulgu.margin*100:.1f}%")
            for sorun in bulgu.sorun_detay:
                rapor.append(f"    {sorun}")
            rapor.append("")
    else:
        rapor.append("\n✅ Tüm kategoriler hedef dahilinde.\n")
    
    # BÖLÜM 2: SEVKİYAT PLANI
    rapor.append("\n" + "─" * 70)
    rapor.append("📦 BÖLÜM 2: SEVKİYAT PLANI")
    rapor.append("─" * 70)
    
    sevk_listesi = [s for s in sku_bulgular if s.aksiyon == "SEVK"]
    
    if sevk_listesi:
        rapor.append(f"\n🚚 {len(sevk_listesi)} SKU ACİL SEVK GEREKTİRİYOR:\n")
        rapor.append(f"{'Önc':^4} | {'SKU Kodu':^12} | {'Ürün Adı':<35} | {'Depo':>8} | {'Mağaza':>8} | {'H.Satış':>8}")
        rapor.append("-" * 95)
        
        for sku in sevk_listesi[:20]:  # İlk 20
            sku_adi_kisalt = sku.sku_adi[:33] + ".." if len(sku.sku_adi) > 35 else sku.sku_adi
            rapor.append(f"{sku.oncelik:^4} | {sku.sku_kod:^12} | {sku_adi_kisalt:<35} | {sku.depo_stok:>8,} | {sku.magaza_stok:>8,} | {sku.haftalik_satis:>8,.0f}")
        
        if len(sevk_listesi) > 20:
            rapor.append(f"\n... ve {len(sevk_listesi) - 20} SKU daha")
    else:
        rapor.append("\n✅ Acil sevkiyat gerektiren SKU yok.\n")
    
    # BÖLÜM 3: İNDİRİM ÖNERİLERİ
    rapor.append("\n" + "─" * 70)
    rapor.append("🏷️ BÖLÜM 3: İNDİRİM / KAMPANYA ÖNERİLERİ")
    rapor.append("─" * 70)
    
    indirim_listesi = [s for s in sku_bulgular if s.aksiyon == "INDIRIM"]
    
    if indirim_listesi:
        rapor.append(f"\n💰 {len(indirim_listesi)} SKU İNDİRİM/KAMPANYA ÖNERİLİYOR:\n")
        rapor.append(f"{'SKU Kodu':^12} | {'Ürün Adı':<35} | {'Cover':>8} | {'H.Satış':>8} | {'Mevcut İO':>10}")
        rapor.append("-" * 85)
        
        for sku in indirim_listesi[:15]:  # İlk 15
            sku_adi_kisalt = sku.sku_adi[:33] + ".." if len(sku.sku_adi) > 35 else sku.sku_adi
            cover_str = f"{sku.cover_hafta:.1f} hf" if sku.cover_hafta < 100 else "∞"
            rapor.append(f"{sku.sku_kod:^12} | {sku_adi_kisalt:<35} | {cover_str:>8} | {sku.haftalik_satis:>8,.0f} | {sku.indirim_orani*100:>9.0f}%")
        
        if len(indirim_listesi) > 15:
            rapor.append(f"\n... ve {len(indirim_listesi) - 15} SKU daha")
    else:
        rapor.append("\n✅ İndirim önerilen SKU yok.\n")
    
    # BÖLÜM 4: LESSONS LEARNED
    rapor.append("\n" + "─" * 70)
    rapor.append("📚 BÖLÜM 4: ÖĞRENILEN DERSLER & STRATEJİK ÖNERİLER")
    rapor.append("─" * 70)
    
    rapor.append("\n📝 Bu Hafta Öğrendiklerimiz:\n")
    
    # Otomatik çıkarımlar
    if sorunlu_kategoriler:
        en_sorunlu = max(sorunlu_kategoriler, key=lambda x: abs(x.butce_sapma))
        rapor.append(f"  1. En sorunlu kategori: {en_sorunlu.kategori} (Bütçe sapması: {en_sorunlu.butce_sapma*100:.1f}%)")
    
    yuksek_cover_kategoriler = [b for b in kategori_bulgular if b.cover > 12]
    if yuksek_cover_kategoriler:
        rapor.append(f"  2. {len(yuksek_cover_kategoriler)} kategoride stok fazlası (Cover > 12 hafta)")
    
    sevk_kritik = [s for s in sevk_listesi if s.oncelik == 1]
    if sevk_kritik:
        rapor.append(f"  3. {len(sevk_kritik)} Top-100 SKU'da acil sevkiyat gerekiyor")
    
    rapor.append("\n🎯 Seneye Bütçe Önerileri:\n")
    
    # Büyüyen kategoriler
    buyuyen = [b for b in kategori_bulgular if b.lfl_degisim > 0.10]
    if buyuyen:
        for b in buyuyen[:3]:
            rapor.append(f"  ↗️ {b.kategori}: LFL +{b.lfl_degisim*100:.1f}% - Bütçe artırımı düşünülebilir")
    
    # Küçülen kategoriler
    kuculen = [b for b in kategori_bulgular if b.lfl_degisim < -0.10]
    if kuculen:
        for b in kuculen[:3]:
            rapor.append(f"  ↘️ {b.kategori}: LFL {b.lfl_degisim*100:.1f}% - Bütçe revizyonu gerekebilir")
    
    rapor.append("\n" + "=" * 70)
    rapor.append("RAPOR SONU")
    rapor.append("=" * 70)
    
    return "\n".join(rapor)

# =============================================================================
# ANA FONKSİYON
# =============================================================================

def calistir(trading_path: str, urun_path: str) -> Tuple[str, pd.DataFrame, pd.DataFrame]:
    """Ana çalıştırma fonksiyonu"""
    
    # 1. Veri yükle
    trading, urun = veri_yukle(trading_path, urun_path)
    
    # 2. Kategori analizi
    kategori_bulgular = kategori_analiz(trading)
    sorunlu_kat_isimleri = [b.kategori for b in kategori_bulgular if b.sorun_var]
    
    # 3. SKU analizi
    sku_bulgular = sku_analiz(urun, sorunlu_kat_isimleri)
    
    # 4. Rapor üret
    rapor = rapor_uret(kategori_bulgular, sku_bulgular)
    
    # 5. Excel çıktıları hazırla
    sevk_df = pd.DataFrame([
        {
            'Öncelik': s.oncelik,
            'SKU Kodu': s.sku_kod,
            'Ürün Adı': s.sku_adi,
            'Kategori': s.kategori,
            'Depo Stok': s.depo_stok,
            'Mağaza Stok': s.magaza_stok,
            'Haftalık Satış': s.haftalik_satis,
            'Cover (Hafta)': round(s.cover_hafta, 1) if s.cover_hafta < 100 else 999
        }
        for s in sku_bulgular if s.aksiyon == "SEVK"
    ])
    
    indirim_df = pd.DataFrame([
        {
            'SKU Kodu': s.sku_kod,
            'Ürün Adı': s.sku_adi,
            'Kategori': s.kategori,
            'Toplam Stok': s.depo_stok + s.magaza_stok,
            'Haftalık Satış': s.haftalik_satis,
            'Cover (Hafta)': round(s.cover_hafta, 1) if s.cover_hafta < 100 else 999,
            'Mevcut İndirim %': round(s.indirim_orani * 100, 0)
        }
        for s in sku_bulgular if s.aksiyon == "INDIRIM"
    ])
    
    return rapor, sevk_df, indirim_df


if __name__ == "__main__":
    # Test
    trading_path = "/mnt/user-data/uploads/trading.xlsx"
    urun_path = "/mnt/user-data/uploads/Ürün_2_hafta.xlsx"
    
    rapor, sevk_df, indirim_df = calistir(trading_path, urun_path)
    print(rapor)
    
    print(f"\n\n📊 Sevkiyat Listesi: {len(sevk_df)} SKU")
    print(f"📊 İndirim Listesi: {len(indirim_df)} SKU")
