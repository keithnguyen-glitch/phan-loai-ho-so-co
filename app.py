import streamlit as st
import re
import io
import zipfile
import pandas as pd
from pypdf import PdfReader, PdfWriter

# --- 1. CẤU HÌNH GIAO DIỆN WEB & ẨN MENU ---
st.set_page_config(page_title="Hệ Thống Tách C/O", page_icon="📄", layout="wide")

# Đoạn CSS này giúp giấu Menu góc trên phải, Footer và làm đẹp giao diện
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            /* Tùy chỉnh làm đẹp khung thông báo */
            div[data-testid="stMetricValue"] {
                font-size: 2rem;
                font-weight: bold;
            }
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- 2. CẤU HÌNH BẢO MẬT & TRẠNG THÁI ---
MAT_KHAU_APP = "madangdeptrai" # Đổi mật khẩu theo ảnh của bạn

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# --- 3. GIAO DIỆN SIDEBAR (THANH BÊN TRÁI) ---
with st.sidebar:
    st.markdown("## 🔐 Xác Thực Hệ Thống")
    
    if not st.session_state.authenticated:
        mat_khau_nhap = st.text_input("Nhập mật khẩu của phòng IMEX để mở khóa:", type="password")
        if mat_khau_nhap:
            if mat_khau_nhap == MAT_KHAU_APP:
                st.session_state.authenticated = True
                st.rerun() # Tải lại trang để vào app
            else:
                st.error("❌ Sai mật khẩu!")
    else:
        st.success("✅ Đã kết nối Danh mục thành công!")
        st.markdown("---")
        st.markdown("### ⚙️ Cài Đặt Nâng Cao")
        tien_to = st.text_input("🔤 Tiền tố mã Hóa đơn", value="V", help="Chữ cái bắt đầu của Invoice. VD: V, VHN, VBB...")
        gop_trang = st.checkbox("🔗 Gộp trang phụ lục tự động", value=True)
        
        if st.button("🚪 Đăng xuất"):
            st.session_state.authenticated = False
            st.rerun()

# --- 4. GIAO DIỆN CHÍNH (MAIN CONTENT) ---
if not st.session_state.authenticated:
    st.title("📋 HỆ THỐNG TÁCH & GỘP FILE C/O TỰ ĐỘNG")
    st.markdown("*Developed by Department of Import Export | Ching Luh Vietnam*")
    st.markdown("---")
    st.info("👈 Vui lòng xác thực hệ thống ở thanh menu bên trái để tiếp tục.")
    st.stop() # Dừng chạy code bên dưới nếu chưa đăng nhập

# Giao diện khi đã đăng nhập
st.title("📋 HỆ THỐNG TÁCH & GỘP FILE C/O TỰ ĐỘNG")
st.markdown("*Developed by Department of Import Export | Ching Luh Vietnam*")
st.markdown("---")

st.markdown("### 📁 Xử lý hàng loạt tài liệu C/O")
st.markdown("Kéo và thả một file PDF chứa nhiều trang C/O vào đây...")

uploaded_file = st.file_uploader("Upload", type="pdf", label_visibility="hidden")

if uploaded_file is not None:
    if st.button("🚀 BẮT ĐẦU XỬ LÝ", use_container_width=True):
        progress_text = "Đang đọc và phân tích dữ liệu file PDF..."
        my_bar = st.progress(0, text=progress_text)
        
        reader = PdfReader(uploaded_file)
        total_pages = len(reader.pages)
        
        pdf_groups = {}
        summary_data = []
        
        last_found_invoice = None
        success_count = 0
        grouped_count = 0
        fail_count = 0

        # --- VÒNG LẶP XỬ LÝ TỪNG TRANG ---
        for i in range(total_pages):
            page = reader.pages[i]
            text = page.extract_text() or ""
            clean_text = re.sub(r'\s+', ' ', text)
            page_num = i + 1
            
            current_invoice = None
            
            # CÁCH 1: Tìm theo pattern đặc trưng
            regex_pattern = rf'\b{tien_to}[A-Z]{{1,3}}\d{{2}}[A-Z0-9]{{4,8}}\b'
            match_pattern = re.search(regex_pattern, clean_text, flags=re.IGNORECASE)
            
            if match_pattern:
                current_invoice = match_pattern.group(0).upper()
            else:
                # CÁCH 2: Tìm dự phòng qua từ khóa "Số hóa đơn" hoặc "Invoice"
                keywords = r'(?:13\.\s*Số hóa đơn\s*:|7\.\s*Invoice|Số hóa đơn\s*:|Invoice\s*(?:No\.?|#)?\s*:)'
                parts = re.split(keywords, clean_text, flags=re.IGNORECASE)
                
                if len(parts) > 1:
                    text_after = parts[1][:200]
                    match_fallback = re.search(r'\b[A-Z0-9]{8,15}\b', text_after, flags=re.IGNORECASE)
                    if match_fallback:
                        current_invoice = match_fallback.group(0).upper()

            # --- LOGIC GỘP NHÓM & GHI NHẬN TRẠNG THÁI ---
            if current_invoice:
                current_invoice = re.sub(r'[\\/*?:"<>|]', "", current_invoice)
                last_found_invoice = current_invoice
                status = "Tìm thấy Mã HĐ"
            else:
                if gop_trang and last_found_invoice:
                    current_invoice = last_found_invoice
                    status = "Gộp vào HĐ trước"
                    grouped_count += 1
                else:
                    current_invoice = f"Trang_{page_num}_KhongXacDinh"
                    status = "Lỗi - Không có mã"
                    fail_count += 1

            if current_invoice not in pdf_groups:
                pdf_groups[current_invoice] = PdfWriter()
                if status == "Tìm thấy Mã HĐ":
                    success_count += 1
            
            pdf_groups[current_invoice].add_page(page)
            
            summary_data.append({
                "Trang số": page_num,
                "File đầu ra (Invoice)": current_invoice if "KhongXacDinh" not in current_invoice else "N/A",
                "Trạng thái": status
            })
            
            my_bar.progress((i + 1) / total_pages, text=f"Đang phân tích: Trang {page_num}/{total_pages}")
        
        # --- ĐÓNG GÓI ZIP ---
        my_bar.progress(1.0, text="Đang đóng gói file ZIP...")
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for inv_num, writer in pdf_groups.items():
                pdf_buffer = io.BytesIO()
                writer.write(pdf_buffer)
                filename = f"{inv_num}.pdf"
                zip_file.writestr(filename, pdf_buffer.getvalue())

        # --- BÁO CÁO KẾT QUẢ KHI XONG ---
        st.markdown("---")
        st.subheader("📊 Kết quả xử lý")
        
        # 3 Cột thống kê nhanh
        col1, col2, col3 = st.columns(3)
        col1.metric("✅ Tìm thấy mã C/O", f"{success_count} file")
        col2.metric("🔗 Phụ lục được gộp", f"{grouped_count} trang")
        col3.metric("⚠️ Lỗi không có mã", f"{fail_count} trang")

        # Nút Download bự
        st.download_button(
            label="📥 TẢI XUỐNG TẤT CẢ FILE ĐÃ TÁCH (.ZIP)",
            data=zip_buffer.getvalue(),
            file_name="HoSo_CO_ChingLuh.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 📋 Bảng Báo Cáo Chi Tiết Từng Trang")
        
        df_summary = pd.DataFrame(summary_data)
        
        # Hàm bôi màu trạng thái trong bảng
        def color_status(val):
            if val == 'Tìm thấy Mã HĐ':
                return 'color: #00b894; font-weight: bold' # Xanh lá
            elif val == 'Gộp vào HĐ trước':
                return 'color: #0984e3' # Xanh dương
            else:
                return 'color: #d63031; font-weight: bold' # Đỏ
            
        # SỬ DỤNG .map() THAY VÌ .applymap() ĐỂ SỬA LỖI PANDAS MỚI
        styled_df = df_summary.style.map(color_status, subset=['Trạng thái'])
        st.dataframe(styled_df, use_container_width=True, height=400)
