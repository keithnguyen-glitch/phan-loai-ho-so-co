import streamlit as st
import re
import io
import zipfile
import pandas as pd
from pypdf import PdfReader, PdfWriter
# --- THƯ VIỆN XỬ LÝ HÌNH ẢNH VÀ OCR CHUYÊN DỤNG ---
from pdf2image import convert_from_bytes
import pytesseract
from PIL import ImageEnhance

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
MAT_KHAU_APP = "Daviddeptrai" 

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
                st.rerun() 
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
    st.stop() 

st.title("📋 HỆ THỐNG TÁCH & GỘP FILE C/O TỰ ĐỘNG")
st.markdown("*Developed by Department of Import Export | Ching Luh Vietnam*")
st.markdown("---")

st.markdown("### 📁 Xử lý hàng loạt tài liệu C/O")
st.markdown("Kéo và thả một hoặc nhiều file PDF chứa các trang C/O vào đây...")

uploaded_files = st.file_uploader("Upload", type="pdf", accept_multiple_files=True, label_visibility="hidden")

if uploaded_files:
    if st.button("🚀 BẮT ĐẦU XỬ LÝ HÀNG LOẠT", use_container_width=True):
        
        total_files = len(uploaded_files)
        st.info(f"📋 Đã tiếp nhận **{total_files}** tệp PDF đầu vào. Tiến hành phân tích cấu trúc...")
        
        pdf_groups = {}
        summary_data = []
        
        success_count = 0
        grouped_count = 0
        fail_count = 0
        total_processed_pages = 0

        # --- LẶP QUA TỪNG FILE ĐƯỢC TẢI LÊN ---
        for file_index, current_file in enumerate(uploaded_files):
            file_bytes = current_file.getvalue()
            reader = PdfReader(current_file)
            file_total_pages = len(reader.pages)
            last_found_invoice = None
            
            st.markdown(f"**⏳ Đang xử lý tệp ({file_index + 1}/{total_files}):** `{current_file.name}`")
            my_bar = st.progress(0, text=f"Đang phân tích dữ liệu tệp...")

            for i in range(file_total_pages):
                page = reader.pages[i]
                page_num = i + 1
                total_processed_pages += 1
                
                text = page.extract_text() or ""
                clean_text = re.sub(r'\s+', ' ', text).strip()
                
                # BỘ LỌC OCR SIÊU NÉT CHO FILE SCAN MỘC ĐỎ
                if len(clean_text) < 40:
                    my_bar.progress(i / file_total_pages, text=f"Đang khử nhiễu mộc đỏ & quét OCR trang {page_num}...")
                    try:
                        # 1. Nâng DPI lên 300 để lấy độ nét cao nhất
                        images = convert_from_bytes(file_bytes, first_page=page_num, last_page=page_num, dpi=300)
                        if images:
                            img = images[0]
                            
                            # 2. Tiền xử lý: Đổi sang ảnh Xám để triệt tiêu màu đỏ của con dấu
                            img = img.convert('L')
                            
                            # 3. Tiền xử lý: Tăng độ tương phản lên 2.0 lần để chữ đen nổi bật lên khỏi nền
                            enhancer = ImageEnhance.Contrast(img)
                            img = enhancer.enhance(2.0)
                            
                            # 4. Đọc chữ từ ảnh đã làm sạch
                            ocr_text = pytesseract.image_to_string(img, lang='eng+vie')
                            clean_text = re.sub(r'\s+', ' ', ocr_text).strip()
                    except Exception as e:
                        st.error(f"Lỗi cục bộ tiến trình OCR tại trang {page_num} của file {current_file.name}: {e}")
                
                current_invoice = None
                
                # Thuật toán Regex tối ưu hóa cho form Ching Luh
                regex_pattern = rf'\b{tien_to}[A-Z]{{2}}\d{{2}}[A-Z0-9]{{5,8}}\b'
                match_pattern = re.search(regex_pattern, clean_text, flags=re.IGNORECASE)
                
                if match_pattern:
                    current_invoice = match_pattern.group(0).upper()
                else:
                    keywords = r'(?:10\.\s*Number\s*and\s*date\s*of\s*invoices?|10\.\s*Invoices?|13\.\s*Số hóa đơn\s*:|7\.\s*Invoice|Invoice\s*(?:No\.?|#)?\s*:?)'
                    parts = re.split(keywords, clean_text, flags=re.IGNORECASE)
                    
                    if len(parts) > 1:
                        text_after = parts[1][:150]
                        # Gom ký tự (chống vỡ chữ do mộc đè)
                        clean_after = re.sub(r'[\s\-]', '', text_after)
                        
                        match_fallback = re.search(rf'{tien_to}[A-Z]{{2}}\d{{2}}[A-Z0-9]{{5,8}}', clean_after, flags=re.IGNORECASE)
                        if match_fallback:
                            current_invoice = match_fallback.group(0).upper()
                        else:
                            match_any = re.search(r'\b[A-Z0-9]{9,15}\b', clean_after, flags=re.IGNORECASE)
                            if match_any:
                                current_invoice = match_any.group(0).upper()

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
                        current_invoice = f"KhongXacDinh_File_{file_index + 1}_Trang_{page_num}"
                        status = "Lỗi - Không có mã"
                        fail_count += 1

                if current_invoice not in pdf_groups:
                    pdf_groups[current_invoice] = PdfWriter()
                    if status == "Tìm thấy Mã HĐ":
                        success_count += 1
                
                pdf_groups[current_invoice].add_page(page)
                
                summary_data.append({
                    "Tên file gốc": current_file.name,
                    "Trang số": page_num,
                    "File đầu ra (Invoice)": current_invoice if "KhongXacDinh" not in current_invoice else "N/A",
                    "Trạng thái": status
                })
                
                my_bar.progress((i + 1) / file_total_pages, text=f"Đang bóc tách: Trang {page_num}/{file_total_pages}")
            
            my_bar.empty() 

        # --- 5. ĐÓNG GÓI THƯ MỤC NÉN ZIP TẢI XUỐNG ---
        st.info("📦 Đang tổng hợp dữ liệu và đóng gói thư mục ZIP...")
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for inv_num, writer in pdf_groups.items():
                pdf_buffer = io.BytesIO()
                writer.write(pdf_buffer)
                filename = f"{inv_num}.pdf"
                zip_file.writestr(filename, pdf_buffer.getvalue())

        # --- 6. GIAO DIỆN BÁO CÁO THỐNG KÊ ---
        st.markdown("---")
        st.success(f"🎉 Hệ thống đã phân loại hoàn tất tổng cộng **{total_processed_pages}** trang từ tất cả chứng từ!")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("✅ Hóa đơn phân loại được", f"{success_count} bộ")
        col2.metric("🔗 Số trang phụ lục đã gộp", f"{grouped_count} trang")
        col3.metric("⚠️ Số trang lỗi mã", f"{fail_count} trang")

        st.download_button(
            label="📥 TẢI XUỐNG TOÀN BỘ FILE HỒ SƠ ĐÃ PHÂN LOẠI (.ZIP)",
            data=zip_buffer.getvalue(),
            file_name="HoSo_CO_ChingLuh_TongHop.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 📋 Bảng Báo Cáo Chi Tiết Tất Cả Các Tệp")
        
        df_summary = pd.DataFrame(summary_data)
        
        def color_status(val):
            if val == 'Tìm thấy Mã HĐ':
                return 'color: #00b894; font-weight: bold' # Xanh lá
            elif val == 'Gộp vào HĐ trước':
                return 'color: #0984e3' # Xanh dương
            else:
                return 'color: #d63031; font-weight: bold' # Đỏ
            
        styled_df = df_summary.style.map(color_status, subset=['Trạng thái'])
        st.dataframe(styled_df, use_container_width=True, height=450)
