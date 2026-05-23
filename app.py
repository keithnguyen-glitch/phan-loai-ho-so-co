import streamlit as st
import re
import io
import zipfile
import pandas as pd
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
st.set_page_config(page_title="Tách PDF Hồ Sơ C/O", page_icon="📄", layout="wide")

# --- SIDEBAR CÀI ĐẶT ---
with st.sidebar:
    st.header("⚙️ Cài Đặt Nâng Cao")
    st.markdown("Tùy chỉnh logic nhận diện và tách file theo nhu cầu thực tế.")
    
    tien_to = st.text_input("🔤 Tiền tố mã Hóa đơn", value="V", help="Chữ cái bắt đầu của Invoice. Ví dụ: V, VHN, VBB...")
    gop_trang = st.checkbox("🔗 Gộp trang phụ lục tự động", value=True, help="Nếu một trang không quét được số Invoice, hệ thống sẽ tự động ghép nó vào chung file PDF với Invoice được tìm thấy ngay trước đó.")

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
            st.markdown("Tải lên file PDF chứa nhiều trang. Hệ thống sẽ tự động tách, gom nhóm và đặt tên theo **Số Hóa Đơn**.")

            # --- LOGIC TÁCH VÀ GỘP PDF ---
            uploaded_file = st.file_uploader("📂 Chọn file PDF gốc tải lên", type="pdf")

            if uploaded_file is not None:
                if st.button("🚀 Bắt đầu xử lý"):
                    # Khởi tạo thanh tiến trình
                    progress_text = "Đang đọc dữ liệu file PDF..."
                    my_bar = st.progress(0, text=progress_text)
                    
                    reader = PdfReader(uploaded_file)
                    total_pages = len(reader.pages)
                    
                    # Dictionary để lưu các trang theo từng Invoice: { 'VHN123': PdfWriter() }
                    pdf_groups = {}
                    summary_data = []
                    
                    last_found_invoice = None
                    success_count = 0
                    fail_count = 0

                    for i in range(total_pages):
                        page = reader.pages[i]
                        text = page.extract_text() or ""
                        clean_text = re.sub(r'\s+', ' ', text)
                        page_num = i + 1
                        
                        current_invoice = None
                        
                        # CÁCH 1: Tìm theo pattern đặc trưng có chứa tiền tố tùy chỉnh
                        # Pattern linh hoạt: Tiền tố + 2-3 chữ cái + 2 số + 4-8 ký tự
                        regex_pattern = rf'\b{tien_to}[A-Z]{{1,3}}\d{{2}}[A-Z0-9]{{4,8}}\b'
                        match_pattern = re.search(regex_pattern, clean_text, flags=re.IGNORECASE)
                        
                        if match_pattern:
                            current_invoice = match_pattern.group(0).upper()
                        else:
                            # CÁCH 2: Quét dự phòng theo từ khóa
                            keywords = r'(?:13\.\s*Số hóa đơn\s*:|7\.\s*Invoice|Số hóa đơn\s*:|Invoice\s*(?:No\.?|#)?\s*:)'
                            parts = re.split(keywords, clean_text, flags=re.IGNORECASE)
                            
                            if len(parts) > 1:
                                text_after = parts[1][:200]
                                match_fallback = re.search(r'\b[A-Z0-9]{8,15}\b', text_after, flags=re.IGNORECASE)
                                if match_fallback:
                                    current_invoice = match_fallback.group(0).upper()

                        # Xử lý Logic Gom Nhóm (Grouping)
                        if current_invoice:
                            # Tìm thấy Invoice trên trang này
                            current_invoice = re.sub(r'[\\/*?:"<>|]', "", current_invoice)
                            last_found_invoice = current_invoice
                            status = "Thành công"
                        else:
                            # Không tìm thấy Invoice
                            if gop_trang and last_found_invoice:
                                current_invoice = last_found_invoice
                                status = "Gộp vào HĐ trước"
                            else:
                                current_invoice = f"Khong_Xac_Dinh_Trang_{page_num}"
                                status = "Thất bại"
                                fail_count += 1

                        # Khởi tạo PdfWriter cho Invoice nếu chưa có
                        if current_invoice not in pdf_groups:
                            pdf_groups[current_invoice] = PdfWriter()
                            if status != "Thất bại":
                                success_count += 1
                        
                        # Thêm trang vào nhóm tương ứng
                        pdf_groups[current_invoice].add_page(page)
                        
                        # Ghi nhận vào báo cáo
                        summary_data.append({
                            "Trang gốc": page_num,
                            "Số Hóa Đơn": current_invoice if status != "Thất bại" else "Không quét được",
                            "Trạng thái": status
                        })
                        
                        # Cập nhật thanh tiến trình
                        progress = (i + 1) / total_pages
                        my_bar.progress(progress, text=f"Đang phân tích: Trang {page_num}/{total_pages}")
                    
                    # Hoàn thành quét -> Nén các file PDF đã gộp vào file ZIP
                    my_bar.progress(1.0, text="Đang đóng gói file ZIP...")
                    zip_buffer = io.BytesIO()
                    
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for inv_num, writer in pdf_groups.items():
                            pdf_buffer = io.BytesIO()
                            writer.write(pdf_buffer)
                            
                            if "Khong_Xac_Dinh" in inv_num:
                                filename = f"{inv_num}.pdf"
                            else:
                                filename = f"{inv_num}.pdf"
                                
                            zip_file.writestr(filename, pdf_buffer.getvalue())

                    # --- GIAO DIỆN KẾT QUẢ ---
                    st.success("🎉 Xử lý hoàn tất!")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"✅ Phát hiện tổng cộng: **{success_count}** Hóa đơn")
                    with col2:
                        st.warning(f"⚠️ Số trang không có mã/lỗi: **{fail_count}** Trang")

                    # Nút tải xuống
                    st.download_button(
                        label="⬇️ TẢI XUỐNG TẤT CẢ FILE ĐÃ TÁCH (.ZIP)",
                        data=zip_buffer.getvalue(),
                        file_name="Ket_Qua_Tach_CO.zip",
                        mime="application/zip",
                        use_container_width=True
                    )

                    # Hiển thị Bảng đối soát
                    st.subheader("📊 Bảng Báo Cáo Chi Tiết")
                    df_summary = pd.DataFrame(summary_data)
                    
                    # Bôi màu cho các trạng thái trong bảng
                    def color_status(val):
                        if val == 'Thành công': return 'color: green'
                        elif val == 'Gộp vào HĐ trước': return 'color: blue'
                        else: return 'color: red'
                        
                    st.dataframe(df_summary.style.applymap(color_status, subset=['Trạng thái']), use_container_width=True)

        else:
            st.session_state.failed_attempts += 1
            attempts_left = GIOI_HAN_SAI - st.session_state.failed_attempts
            
            if attempts_left > 0:
                st.error(f"❌ Mật khẩu không chính xác! Bạn còn **{attempts_left}** lần thử.")
            else:
                st.session_state.locked_out = True
                st.rerun()