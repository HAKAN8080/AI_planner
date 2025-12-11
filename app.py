"""
SANAL PLANNER - Streamlit Arayüzü
EVE Kozmetik için Agentic Retail Planning Assistant
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from planner_agent import calistir, KURALLAR, kategori_analiz, sku_analiz, veri_yukle

# Sayfa ayarları
st.set_page_config(
    page_title="Sanal Planner | EVE Kozmetik",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E3A8A;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #6B7280;
        margin-top: 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
    }
    .alert-box {
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
    }
    .alert-critical { background-color: #FEE2E2; border-left: 4px solid #DC2626; }
    .alert-warning { background-color: #FEF3C7; border-left: 4px solid #F59E0B; }
    .alert-success { background-color: #D1FAE5; border-left: 4px solid #10B981; }
</style>
""", unsafe_allow_html=True)

# Header
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown('<p class="main-header">🤖 Sanal Planner</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">EVE Kozmetik | Agentic Retail Planning Assistant</p>', unsafe_allow_html=True)
with col2:
    st.markdown(f"**📅 {datetime.now().strftime('%d.%m.%Y')}**")

st.markdown("---")

# Sidebar - Kural Ayarları
with st.sidebar:
    st.header("⚙️ Kural Ayarları")
    
    st.subheader("📊 Bütçe")
    butce_sapma = st.slider(
        "Kritik sapma eşiği (%)", 
        min_value=10, max_value=50, 
        value=int(KURALLAR["butce_sapma_kritik"] * 100),
        help="Bu oranın üzerinde sapma kritik kabul edilir"
    )
    
    st.subheader("📦 Cover Hedefleri")
    cover_depo = st.slider("Depo cover hedefi (hafta)", 8, 20, KURALLAR["cover_depo_hedef"])
    cover_mag_min = st.slider("Mağaza min cover (hafta)", 4, 12, KURALLAR["cover_magaza_min"])
    cover_mag_max = st.slider("Mağaza max cover (hafta)", 8, 20, KURALLAR["cover_magaza_max"])
    
    st.subheader("🚚 Sevkiyat")
    sevk_cover = st.slider("Sevk tetikleyici (mağaza cover altı)", 2, 8, 4)
    
    st.subheader("🏷️ İndirim")
    indirim_cover = st.slider("İndirim tetikleyici (cover üstü)", 15, 40, 20)
    
    st.subheader("⭐ Top SKU")
    top_sku = st.slider("Top SKU sayısı", 50, 200, KURALLAR["top_sku_sayisi"])
    
    # Kuralları güncelle
    if st.button("💾 Kuralları Uygula", use_container_width=True):
        KURALLAR["butce_sapma_kritik"] = butce_sapma / 100
        KURALLAR["cover_depo_hedef"] = cover_depo
        KURALLAR["cover_magaza_min"] = cover_mag_min
        KURALLAR["cover_magaza_max"] = cover_mag_max
        KURALLAR["top_sku_sayisi"] = top_sku
        st.success("✅ Kurallar güncellendi!")

# Ana içerik
tab1, tab2, tab3, tab4 = st.tabs(["📤 Veri Yükle", "📊 Analiz", "📦 Sevkiyat", "🏷️ İndirim"])

# TAB 1: Veri Yükleme
with tab1:
    st.header("📤 Haftalık Raporları Yükle")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Trading Raporu")
        trading_file = st.file_uploader(
            "Kategori bazlı trading raporu (Excel)",
            type=['xlsx', 'xls'],
            key="trading"
        )
        if trading_file:
            st.success(f"✅ {trading_file.name} yüklendi")
    
    with col2:
        st.subheader("Ürün Raporu")
        urun_file = st.file_uploader(
            "SKU bazlı ürün raporu (Excel)",
            type=['xlsx', 'xls'],
            key="urun"
        )
        if urun_file:
            st.success(f"✅ {urun_file.name} yüklendi")
    
    if trading_file and urun_file:
        if st.button("🚀 Analizi Başlat", type="primary", use_container_width=True):
            with st.spinner("🤖 Sanal Planner analiz ediyor..."):
                # Dosyaları geçici kaydet
                import tempfile
                import os
                
                with tempfile.TemporaryDirectory() as tmpdir:
                    trading_path = os.path.join(tmpdir, "trading.xlsx")
                    urun_path = os.path.join(tmpdir, "urun.xlsx")
                    
                    with open(trading_path, 'wb') as f:
                        f.write(trading_file.getvalue())
                    with open(urun_path, 'wb') as f:
                        f.write(urun_file.getvalue())
                    
                    # Analiz çalıştır
                    rapor, sevk_df, indirim_df = calistir(trading_path, urun_path)
                    
                    # Veriyi session'a kaydet (to_dict kullanarak)
                    trading_df, urun_df = veri_yukle(trading_path, urun_path)
                    st.session_state['trading_dict'] = trading_df.to_dict('records')
                    st.session_state['trading_cols'] = list(trading_df.columns)
                    st.session_state['rapor'] = rapor
                    st.session_state['sevk_dict'] = sevk_df.to_dict('records')
                    st.session_state['sevk_cols'] = list(sevk_df.columns)
                    st.session_state['indirim_dict'] = indirim_df.to_dict('records')
                    st.session_state['indirim_cols'] = list(indirim_df.columns)
                    st.session_state['analiz_yapildi'] = True
            
            st.success("✅ Analiz tamamlandı! Diğer sekmelere geçebilirsin.")
            st.balloons()

# TAB 2: Analiz Sonuçları
with tab2:
    st.header("📊 Analiz Sonuçları")
    
    if 'analiz_yapildi' not in st.session_state:
        st.info("⬆️ Önce 'Veri Yükle' sekmesinden dosyaları yükle ve analizi başlat.")
    else:
        # Özet metrikler
        sevk_df = pd.DataFrame(st.session_state['sevk_dict'])
        indirim_df = pd.DataFrame(st.session_state['indirim_dict'])
        trading = pd.DataFrame(st.session_state['trading_dict'])
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            kritik_kat = len([1 for _, r in trading.iterrows() 
                           if abs(r.get('Achieved TY Sales Budget Value TRY', 0) or 0) >= KURALLAR["butce_sapma_kritik"]])
            st.metric("🔴 Kritik Kategori", kritik_kat)
        
        with col2:
            st.metric("🚚 Sevk Gereken SKU", len(sevk_df))
        
        with col3:
            st.metric("🏷️ İndirim Önerilen SKU", len(indirim_df))
        
        with col4:
            top_sevk = len(sevk_df[sevk_df['Öncelik'] == 1]) if len(sevk_df) > 0 else 0
            st.metric("⭐ Öncelik 1 (Top SKU)", top_sevk)
        
        st.markdown("---")
        
        # Rapor görüntüle
        st.subheader("📝 Detaylı Rapor")
        
        with st.expander("Tam Raporu Görüntüle", expanded=True):
            st.text(st.session_state['rapor'])
        
        # Rapor indirme
        st.download_button(
            label="📥 Raporu İndir (TXT)",
            data=st.session_state['rapor'],
            file_name=f"sanal_planner_rapor_{datetime.now().strftime('%Y%m%d')}.txt",
            mime="text/plain"
        )

# TAB 3: Sevkiyat Planı
with tab3:
    st.header("📦 Sevkiyat Planı")
    
    if 'sevk_dict' not in st.session_state:
        st.info("⬆️ Önce 'Veri Yükle' sekmesinden analizi başlat.")
    else:
        sevk_df = pd.DataFrame(st.session_state['sevk_dict'])
        
        if len(sevk_df) == 0:
            st.success("✅ Acil sevkiyat gerektiren SKU bulunmuyor.")
        else:
            # Filtreler
            col1, col2, col3 = st.columns(3)
            
            with col1:
                oncelik_filter = st.multiselect(
                    "Öncelik", 
                    options=[1, 2, 3],
                    default=[1, 2],
                    format_func=lambda x: {1: "🔴 Kritik", 2: "🟡 Yüksek", 3: "🟢 Normal"}[x]
                )
            
            with col2:
                if 'Kategori' in sevk_df.columns:
                    kategoriler = sevk_df['Kategori'].unique().tolist()
                    kat_filter = st.multiselect("Kategori", options=kategoriler, default=kategoriler[:5])
                else:
                    kat_filter = None
            
            with col3:
                min_satis = st.number_input("Min Haftalık Satış", value=0, step=10)
            
            # Filtrele
            filtered_df = sevk_df[sevk_df['Öncelik'].isin(oncelik_filter)]
            if kat_filter:
                filtered_df = filtered_df[filtered_df['Kategori'].isin(kat_filter)]
            filtered_df = filtered_df[filtered_df['Haftalık Satış'] >= min_satis]
            
            st.markdown(f"**{len(filtered_df)} SKU listeleniyor**")
            
            # Tablo
            st.dataframe(
                filtered_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Öncelik": st.column_config.NumberColumn("Öncelik", format="%d"),
                    "Depo Stok": st.column_config.NumberColumn("Depo Stok", format="%d"),
                    "Mağaza Stok": st.column_config.NumberColumn("Mağaza Stok", format="%d"),
                    "Haftalık Satış": st.column_config.NumberColumn("H.Satış", format="%.0f"),
                    "Cover (Hafta)": st.column_config.NumberColumn("Cover", format="%.1f"),
                }
            )
            
            # Excel indirme
            import io
            buffer = io.BytesIO()
            filtered_df.to_excel(buffer, index=False, engine='openpyxl')
            
            st.download_button(
                label="📥 Sevkiyat Listesini İndir (Excel)",
                data=buffer.getvalue(),
                file_name=f"sevkiyat_plani_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# TAB 4: İndirim Önerileri
with tab4:
    st.header("🏷️ İndirim / Kampanya Önerileri")
    
    if 'indirim_dict' not in st.session_state:
        st.info("⬆️ Önce 'Veri Yükle' sekmesinden analizi başlat.")
    else:
        indirim_df = pd.DataFrame(st.session_state['indirim_dict'])
        
        if len(indirim_df) == 0:
            st.success("✅ İndirim önerilen SKU bulunmuyor.")
        else:
            # Filtreler
            col1, col2, col3 = st.columns(3)
            
            with col1:
                min_cover = st.slider("Min Cover (Hafta)", 12, 100, 20)
            
            with col2:
                max_satis = st.number_input("Max Haftalık Satış", value=50, step=10)
            
            with col3:
                if 'Kategori' in indirim_df.columns:
                    kategoriler = indirim_df['Kategori'].unique().tolist()
                    kat_filter_ind = st.multiselect("Kategori", options=kategoriler, default=kategoriler[:5], key="ind_kat")
                else:
                    kat_filter_ind = None
            
            # Filtrele
            filtered_ind = indirim_df[
                (indirim_df['Cover (Hafta)'] >= min_cover) &
                (indirim_df['Haftalık Satış'] <= max_satis)
            ]
            if kat_filter_ind:
                filtered_ind = filtered_ind[filtered_ind['Kategori'].isin(kat_filter_ind)]
            
            st.markdown(f"**{len(filtered_ind)} SKU listeleniyor**")
            
            # Tablo
            st.dataframe(
                filtered_ind.head(100),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Toplam Stok": st.column_config.NumberColumn("Stok", format="%d"),
                    "Haftalık Satış": st.column_config.NumberColumn("H.Satış", format="%.0f"),
                    "Cover (Hafta)": st.column_config.NumberColumn("Cover", format="%.1f"),
                    "Mevcut İndirim %": st.column_config.NumberColumn("İndirim %", format="%.0f%%"),
                }
            )
            
            if len(filtered_ind) > 100:
                st.caption(f"İlk 100 gösteriliyor. Toplam: {len(filtered_ind)}")
            
            # Excel indirme
            buffer = io.BytesIO()
            filtered_ind.to_excel(buffer, index=False, engine='openpyxl')
            
            st.download_button(
                label="📥 İndirim Listesini İndir (Excel)",
                data=buffer.getvalue(),
                file_name=f"indirim_onerileri_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #6B7280; font-size: 0.9rem;'>
        🤖 Sanal Planner v1.0 | Thorius AR4U Ekosistemi | EVE Kozmetik
    </div>
    """, 
    unsafe_allow_html=True
)
