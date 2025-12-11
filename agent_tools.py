"""
SANAL PLANNER - Agentic Tool Calling
Claude API ile küp verisini sorgulayan akıllı agent
"""

import pandas as pd
import numpy as np
import json
from typing import Optional
import anthropic

# =============================================================================
# KÜPÜ SİMÜLE EDEN VERİ FONKSİYONLARI
# =============================================================================

class KupVeri:
    """Küp verisini yöneten sınıf"""
    
    def __init__(self, trading_path: str, urun_path: str):
        self.trading = pd.read_excel(trading_path, sheet_name='mtd')
        self.urun = pd.read_excel(urun_path)
        self._hazirla()
    
    def _hazirla(self):
        """Veriyi hazırla"""
        # Ürün verisinde cover hesapla
        self.urun['haftalik_satis'] = (
            self.urun['TW Adet'].fillna(0) + self.urun['LW Adet'].fillna(0)
        ) / 2
        self.urun['toplam_stok'] = (
            self.urun['Anlık Depo Stok Adet'].fillna(0) + 
            self.urun['Anlık Mğz Stok Adet'].fillna(0)
        )
        self.urun['cover_hafta'] = np.where(
            self.urun['haftalik_satis'] > 0,
            self.urun['toplam_stok'] / self.urun['haftalik_satis'],
            999
        )


def genel_ozet(kup: KupVeri) -> str:
    """Genel özet - tüm kategorilerin durumu"""
    
    sonuc = []
    sonuc.append("=== GENEL ÖZET ===\n")
    
    for _, row in kup.trading.iterrows():
        kategori = row['Satır Etiketleri']
        if pd.isna(kategori):
            continue
            
        butce_sapma = row.get('Achieved TY Sales Budget Value TRY', 0) or 0
        cover = row.get('TY Store Back Cover', 0) or 0
        lfl = row.get('LFL Sales Value TYvsLY LC%', 0) or 0
        
        durum = "✅" if abs(butce_sapma) < 0.15 else "🔴"
        
        sonuc.append(f"{durum} {kategori}")
        sonuc.append(f"   Bütçe Sapma: {butce_sapma*100:.1f}% | Cover: {cover:.1f} hf | LFL: {lfl*100:.1f}%")
    
    return "\n".join(sonuc)


def kategori_analiz(kup: KupVeri, kategori: str) -> str:
    """Belirli bir kategorinin detaylı analizi"""
    
    # Kategori filtrele
    kat_urun = kup.urun[kup.urun['Kategori '].str.contains(kategori, case=False, na=False)]
    
    if len(kat_urun) == 0:
        return f"'{kategori}' kategorisi bulunamadı."
    
    sonuc = []
    sonuc.append(f"=== {kategori.upper()} KATEGORİ ANALİZİ ===\n")
    sonuc.append(f"Toplam SKU: {len(kat_urun)}")
    sonuc.append(f"Toplam Stok: {kat_urun['toplam_stok'].sum():,.0f} adet")
    sonuc.append(f"Haftalık Satış: {kat_urun['haftalik_satis'].sum():,.0f} adet")
    sonuc.append(f"Ortalama Cover: {kat_urun['cover_hafta'].median():.1f} hafta")
    
    # Alt kategori (ÜMG) bazlı kırılım
    sonuc.append("\n--- Alt Kategori Kırılımı (ÜMG) ---")
    umg_grup = kat_urun.groupby('ÜMG').agg({
        'Ürün Kodu': 'count',
        'toplam_stok': 'sum',
        'haftalik_satis': 'sum'
    }).reset_index()
    umg_grup.columns = ['ÜMG', 'SKU_Sayisi', 'Stok', 'Satis']
    umg_grup['Cover'] = umg_grup['Stok'] / (umg_grup['Satis'] + 0.1)
    
    for _, row in umg_grup.iterrows():
        durum = "🔴" if row['Cover'] > 15 else "✅"
        sonuc.append(f"{durum} {row['ÜMG']}: {row['SKU_Sayisi']} SKU, Cover: {row['Cover']:.1f} hf")
    
    # Sorunlu SKU'lar
    sorunlu = kat_urun[kat_urun['cover_hafta'] > 20].head(10)
    if len(sorunlu) > 0:
        sonuc.append(f"\n--- Yüksek Cover'lı SKU'lar (İndirim Adayı) ---")
        for _, row in sorunlu.iterrows():
            sonuc.append(f"  {row['Ürün Kodu']} | Cover: {row['cover_hafta']:.0f} hf | Stok: {row['toplam_stok']:.0f}")
    
    # Sevk gereken SKU'lar
    sevk_aday = kat_urun[
        (kat_urun['Anlık Depo Stok Adet'].fillna(0) > 100) &
        (kat_urun['Anlık Mğz Stok Adet'].fillna(0) < kat_urun['haftalik_satis'] * 3)
    ].head(10)
    if len(sevk_aday) > 0:
        sonuc.append(f"\n--- Sevk Edilmesi Gereken SKU'lar ---")
        for _, row in sevk_aday.iterrows():
            sonuc.append(f"  {row['Ürün Kodu']} | Depo: {row['Anlık Depo Stok Adet']:.0f} | Mağaza: {row['Anlık Mğz Stok Adet']:.0f}")
    
    return "\n".join(sonuc)


def sku_detay(kup: KupVeri, sku_kod: str) -> str:
    """Belirli bir SKU'nun detayı"""
    
    sku = kup.urun[kup.urun['Ürün Kodu'].astype(str) == str(sku_kod)]
    
    if len(sku) == 0:
        return f"SKU '{sku_kod}' bulunamadı."
    
    row = sku.iloc[0]
    
    sonuc = []
    sonuc.append(f"=== SKU DETAY: {sku_kod} ===\n")
    sonuc.append(f"Ürün: {row.get('Ürün ', 'N/A')}")
    sonuc.append(f"Kategori: {row.get('Kategori ', 'N/A')}")
    sonuc.append(f"ÜMG: {row.get('ÜMG', 'N/A')}")
    sonuc.append(f"Marka: {row.get('Marka ', 'N/A')}")
    sonuc.append(f"\n--- Stok Durumu ---")
    sonuc.append(f"Depo Stok: {row.get('Anlık Depo Stok Adet', 0):,.0f} adet")
    sonuc.append(f"Mağaza Stok: {row.get('Anlık Mğz Stok Adet', 0):,.0f} adet")
    sonuc.append(f"Toplam Stok: {row['toplam_stok']:,.0f} adet")
    sonuc.append(f"\n--- Satış ---")
    sonuc.append(f"Bu Hafta: {row.get('TW Adet', 0):,.0f} adet")
    sonuc.append(f"Geçen Hafta: {row.get('LW Adet', 0):,.0f} adet")
    sonuc.append(f"Haftalık Ort: {row['haftalik_satis']:,.0f} adet")
    sonuc.append(f"\n--- Metrikler ---")
    sonuc.append(f"Cover: {row['cover_hafta']:.1f} hafta")
    sonuc.append(f"İndirim Oranı: {row.get('TW İO', 0)*100:.0f}%")
    
    # Öneri
    sonuc.append(f"\n--- ÖNERİ ---")
    if row['cover_hafta'] > 20:
        sonuc.append("🔴 Cover yüksek - İNDİRİM veya KAMPANYA önerilir")
    elif row.get('Anlık Depo Stok Adet', 0) > 100 and row.get('Anlık Mğz Stok Adet', 0) < row['haftalik_satis'] * 2:
        sonuc.append("🟡 Mağazada stok düşük - SEVKİYAT önerilir")
    else:
        sonuc.append("✅ Stok dengeli - İzlemeye devam")
    
    return "\n".join(sonuc)


def sorunlu_bul(kup: KupVeri, sorun_tipi: str = "hepsi") -> str:
    """Sorunlu SKU'ları bul
    
    sorun_tipi: "yuksek_cover", "sevk_gerekli", "yok_satis", "hepsi"
    """
    
    sonuc = []
    sonuc.append(f"=== SORUNLU SKU TARAMASI ({sorun_tipi}) ===\n")
    
    if sorun_tipi in ["yuksek_cover", "hepsi"]:
        yuksek = kup.urun[kup.urun['cover_hafta'] > 20].nlargest(15, 'cover_hafta')
        sonuc.append(f"--- Yüksek Cover (>20 hafta) - İndirim Adayı ---")
        sonuc.append(f"Toplam: {len(kup.urun[kup.urun['cover_hafta'] > 20])} SKU\n")
        for _, row in yuksek.iterrows():
            sonuc.append(f"  {row['Ürün Kodu']} | {row.get('Kategori ', '')[:20]} | Cover: {row['cover_hafta']:.0f} hf")
    
    if sorun_tipi in ["sevk_gerekli", "hepsi"]:
        sevk = kup.urun[
            (kup.urun['Anlık Depo Stok Adet'].fillna(0) > 200) &
            (kup.urun['Anlık Mğz Stok Adet'].fillna(0) < kup.urun['haftalik_satis'] * 2) &
            (kup.urun['haftalik_satis'] > 20)
        ].nlargest(15, 'haftalik_satis')
        sonuc.append(f"\n--- Sevk Gerekli (Depoda var, mağazada az) ---")
        sonuc.append(f"Toplam: {len(sevk)} SKU\n")
        for _, row in sevk.iterrows():
            sonuc.append(f"  {row['Ürün Kodu']} | Depo: {row['Anlık Depo Stok Adet']:.0f} | Mğz: {row['Anlık Mğz Stok Adet']:.0f} | Satış: {row['haftalik_satis']:.0f}/hf")
    
    if sorun_tipi in ["dusuk_satis", "hepsi"]:
        dusuk = kup.urun[
            (kup.urun['toplam_stok'] > 500) &
            (kup.urun['haftalik_satis'] < 5)
        ].nlargest(15, 'toplam_stok')
        sonuc.append(f"\n--- Düşük Satış (Stok var, satış yok) ---")
        sonuc.append(f"Toplam: {len(dusuk)} SKU\n")
        for _, row in dusuk.iterrows():
            sonuc.append(f"  {row['Ürün Kodu']} | Stok: {row['toplam_stok']:.0f} | Satış: {row['haftalik_satis']:.1f}/hf")
    
    return "\n".join(sonuc)


# =============================================================================
# CLAUDE AGENT - TOOL CALLING
# =============================================================================

TOOLS = [
    {
        "name": "genel_ozet",
        "description": "Tüm kategorilerin genel durumunu gösterir. Bütçe sapması, cover ve LFL bilgilerini içerir. Analize başlarken ilk çağrılması gereken araç.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "kategori_analiz",
        "description": "Belirli bir kategorinin detaylı analizini yapar. Alt kategori kırılımı, sorunlu SKU'lar ve sevk adaylarını gösterir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "kategori": {
                    "type": "string",
                    "description": "Analiz edilecek kategori adı. Örn: 'RENKLİ KOZMETİK', 'SAÇ BAKIM', 'CİLT BAKIM'"
                }
            },
            "required": ["kategori"]
        }
    },
    {
        "name": "sku_detay",
        "description": "Belirli bir SKU'nun tüm detaylarını gösterir. Stok, satış, cover ve öneri içerir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sku_kod": {
                    "type": "string",
                    "description": "Detayı istenen SKU kodu. Örn: '1032437'"
                }
            },
            "required": ["sku_kod"]
        }
    },
    {
        "name": "sorunlu_bul",
        "description": "Belirli tipteki sorunlu SKU'ları tarar ve listeler.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sorun_tipi": {
                    "type": "string",
                    "enum": ["yuksek_cover", "sevk_gerekli", "dusuk_satis", "hepsi"],
                    "description": "Aranacak sorun tipi. 'yuksek_cover': İndirim adayları, 'sevk_gerekli': Depoda var mağazada yok, 'dusuk_satis': Stok var satış yok, 'hepsi': Tüm sorunlar"
                }
            },
            "required": ["sorun_tipi"]
        }
    }
]

SYSTEM_PROMPT = """Sen EVE Kozmetik için çalışan deneyimli bir Retail Planner'sın. Adın "Sanal Planner".

Görevin haftalık verileri analiz edip şu kararları vermek:
1. Sevkiyat stratejisi (hangi ürünler depolardan mağazalara gönderilmeli)
2. İndirim/kampanya kararları (hangi ürünlere indirim yapılmalı)
3. Öğrenilen dersler (seneye bütçeye ne eklemeliyiz)
4. SKU dağılımı önerileri

Analiz yaparken şu kuralları uygula:
- Bütçe sapması %30'un üzerindeyse KRİTİK
- Cover 12 haftanın üzerindeyse FAZLA STOK
- Cover 4 haftanın altındaysa STOK RİSKİ
- Top 100 SKU'da yok satışa tolerans YOK

Çalışma şeklin:
1. Önce genel_ozet ile büyük resme bak
2. Sorunlu kategorileri tespit et
3. kategori_analiz ile detaya in
4. Gerekirse sku_detay ile SKU seviyesine in
5. sorunlu_bul ile sistematik tarama yap

Türkçe yanıt ver. Bulgularını net ve aksiyona dönük şekilde sun."""


def agent_calistir(api_key: str, kup: KupVeri, kullanici_mesaji: str) -> str:
    """Agent'ı çalıştır ve sonuç al"""
    
    client = anthropic.Anthropic(api_key=api_key)
    
    messages = [{"role": "user", "content": kullanici_mesaji}]
    
    tum_cevaplar = []
    max_iterasyon = 10
    iterasyon = 0
    
    while iterasyon < max_iterasyon:
        iterasyon += 1
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )
        
        # Tool kullanımı var mı kontrol et
        tool_kullanimi = False
        
        for block in response.content:
            if block.type == "text":
                tum_cevaplar.append(block.text)
            
            elif block.type == "tool_use":
                tool_kullanimi = True
                tool_name = block.name
                tool_input = block.input
                tool_use_id = block.id
                
                # Tool'u çağır
                if tool_name == "genel_ozet":
                    tool_result = genel_ozet(kup)
                elif tool_name == "kategori_analiz":
                    tool_result = kategori_analiz(kup, tool_input.get("kategori", ""))
                elif tool_name == "sku_detay":
                    tool_result = sku_detay(kup, tool_input.get("sku_kod", ""))
                elif tool_name == "sorunlu_bul":
                    tool_result = sorunlu_bul(kup, tool_input.get("sorun_tipi", "hepsi"))
                else:
                    tool_result = f"Bilinmeyen araç: {tool_name}"
                
                # Mesajlara ekle
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": tool_result
                    }]
                })
        
        # Tool kullanımı yoksa döngüden çık
        if not tool_kullanimi or response.stop_reason == "end_turn":
            break
    
    return "\n".join(tum_cevaplar)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    import os
    
    # Test için
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    
    if not api_key:
        print("ANTHROPIC_API_KEY environment variable gerekli!")
        print("Kullanım: ANTHROPIC_API_KEY=sk-... python agent_tools.py")
    else:
        # Veriyi yükle
        kup = KupVeri(
            "/mnt/user-data/uploads/trading.xlsx",
            "/mnt/user-data/uploads/Ürün_2_hafta.xlsx"
        )
        
        # Agent'ı çalıştır
        sonuc = agent_calistir(
            api_key, 
            kup, 
            "Bu haftanın analizini yap. Önce genel duruma bak, sorunlu kategorileri bul, detaya in ve aksiyon önerileri sun."
        )
        
        print(sonuc)
