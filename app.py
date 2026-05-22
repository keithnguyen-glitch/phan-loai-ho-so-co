import streamlit as st
import re
import io
import zipfile
from pypdf import PdfReader, PdfWriter

# --- GIAO DIỆN WEB ---
st.set_page_config(page_title="Tách PDF Hồ Sơ C/O", page_icon="📄")
st.title("📄 Công Cụ Tách PDF Hồ Sơ C/O Tự Động")
st.markdown("Tải lên file PDF chứa nhiều trang, hệ thống sẽ tự động tách và đặt tên theo **Số Hóa Đơn**.")

# Nút tải file
uploaded_file = st.file_uploader("Chọn file PDF gốc tải lên", type="pdf")

if uploaded_file is not None:
    if st.button("🚀 Bắt đầu tách file"):
        with st.spinner("Đang xử lý dữ liệu, vui lòng đợi..."):
            
            # Khởi tạo bộ nhớ tạm để tạo file ZIP
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
                    
                    # Trích xuất mã hóa đơn bằng Regex
                    invoice_num = None
                    parts = re.split(r'(?:13\.\s*)?Số hóa đơn:', text, flags=re.IGNORECASE)
                    
                    if len(parts) > 1:
                        text_after = parts[1][:500]
                        match = re.search(r'\b[A-Z]{2,5}\d{2,}[A-Z0-9]*\b', text_after, flags=re.IGNORECASE)
                        if match:
                            invoice_num = match.group(0).upper()
                    
                    # Đặt tên file (thêm số trang ở cuối để tránh trùng lặp tên trong file nén)
                    if invoice_num:
                        filename = f"Invoice_{invoice_num}_Trang{page_num}.pdf"
                        success_count += 1
                    else:
                        filename = f"Trang_{page_num}_Khong_Quet_Duoc_So_HD.pdf"
                        fail_count += 1
                        
                    # Tạo trang PDF mới và lưu vào bộ nhớ tạm
                    writer = PdfWriter()
                    writer.add_page(page)
                    pdf_buffer = io.BytesIO()
                    writer.write(pdf_buffer)
                    
                    # Đưa trang PDF vào file ZIP
                    zip_file.writestr(filename, pdf_buffer.getvalue())
            
            # Báo cáo kết quả
            st.success(f"🎉 Đã xử lý xong {total_pages} trang!")
            st.info(f"✅ Nhận diện thành công: {success_count} trang | ⚠️ Không thấy mã: {fail_count} trang")
            
            # Nút tải xuống file ZIP
            st.download_button(
                label="⬇️ TẢI XUỐNG TẤT CẢ (File .zip)",
                data=zip_buffer.getvalue(),
                file_name="Ho_So_CO_Da_Tach.zip",
                mime="application/zip"
            )