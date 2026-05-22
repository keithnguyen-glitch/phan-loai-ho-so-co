import streamlit as st
import re
import io
import zipfile
from pypdf import PdfReader, PdfWriter

# --- CẤU HÌNH BẢO MẬT ---
MAT_KHAU_APP = "XNK123" # Đổi mật khẩu tại đây
GIOI_HAN_SAI = 5        # Số lần nhập sai tối đa

# --- KHỞI TẠO BỘ NHỚ TẠM (SESSION STATE) ---
if 'failed_attempts' not in st.session_state:
    st.session_state.failed_attempts = 0
if 'locked_out' not in st.session_state:
    st.session_state.locked_out = False

# --- GIAO DIỆN WEB ---
st.set_page_config(page_title="Tách PDF Hồ Sơ C/O", page_icon="📄")
st.title("📄 Công Cụ Tách PDF Hồ Sơ C/O Tự Động")

# 1. KIỂM TRA TRẠNG THÁI KHÓA
if st.session_state.locked_out:
    st.error("🚫 HỆ THỐNG ĐÃ BỊ KHÓA!")
    st.markdown("Bạn đã nhập sai mật khẩu quá số lần quy định. Vui lòng tải lại trang (F5) hoặc liên hệ Quản trị viên để được hỗ trợ.")
else:
    # 2. XỬ LÝ NHẬP MẬT KHẨU
    mat_khau_nhap = st.text_input("🔒 Vui lòng nhập mật khẩu do quản trị viên cung cấp:", type="password")

    if mat_khau_nhap:
        if mat_khau_nhap == MAT_KHAU_APP:
            st.session_state.failed_attempts = 0 
            st.success("🔓 Đăng nhập thành công!")
            st.markdown("Tải lên file PDF chứa nhiều trang, hệ thống sẽ tự động tách và đặt tên theo **Số Hóa Đơn**.")

            uploaded_file = st.file_uploader("Chọn file PDF gốc tải lên", type="pdf")

            if uploaded_file is not None:
                if st.button("🚀 Bắt đầu tách file"):
                    with st.spinner("Đang xử lý dữ liệu, vui lòng đợi..."):
                        
                        zip_buffer = io.BytesIO()
                        
                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                            reader = PdfReader(uploaded_file)
                            total_pages = len(reader.pages)
                            
                            success_count = 0
                            fail_count = 0
                            
                            for i in range(total_pages):
                                page = reader.pages[i]
                                text = page.extract_text() or ""
                                page_num = i + 1
                                
                                invoice_num = None
                                parts = re.split(r'(?:13\.\s*)?Số hóa đơn:', text, flags=re.IGNORECASE)
                                
                                if len(parts) > 1:
                                    text_after = parts[1][:500]
                                    match = re.search(r'\b[A-Z]{2,5}\d{2,}[A-Z0-9]*\b', text_after, flags=re.IGNORECASE)
                                    if match:
                                        invoice_num = match.group(0).upper()
                                
                                # ĐẶT TÊN FILE GỌN GÀNG THEO YÊU CẦU
                                if invoice_num:
                                    filename = f"{invoice_num}.pdf"
                                    success_count += 1
                                else:
                                    filename = f"Khong_Quet_Duoc_So_HD_Trang_{page_num}.pdf"
                                    fail_count += 1
                                
                                # Xử lý chống mất dữ liệu khi có 2 trang trùng 1 số Hóa đơn
                                original_filename = filename
                                counter = 2
                                while filename in zip_file.namelist():
                                    name_part = original_filename.replace('.pdf', '')
                                    filename = f"{name_part}_{counter}.pdf"
                                    counter += 1
                                    
                                writer = PdfWriter()
                                writer.add_page(page)
                                pdf_buffer = io.BytesIO()
                                writer.write(pdf_buffer)
                                
                                zip_file.writestr(filename, pdf_buffer.getvalue())
                        
                        st.success(f"🎉 Đã xử lý xong {total_pages} trang!")
                        st.info(f"✅ Nhận diện thành công: {success_count} trang | ⚠️ Không thấy mã: {fail_count} trang")
                        
                        st.download_button(
                            label="⬇️ TẢI XUỐNG TẤT CẢ (File .zip)",
                            data=zip_buffer.getvalue(),
                            file_name="Ho_So_CO_Da_Tach.zip",
                            mime="application/zip"
                        )
        else:
            st.session_state.failed_attempts += 1
            attempts_left = GIOI_HAN_SAI - st.session_state.failed_attempts
            
            if attempts_left > 0:
                st.error(f"❌ Mật khẩu không chính xác! Bạn còn **{attempts_left}** lần thử.")
            else:
                st.session_state.locked_out = True
                st.rerun()
