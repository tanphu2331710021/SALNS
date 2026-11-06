import streamlit as st
import pandas as pd
# Import đúng hàm từ file thuật toán của bạn
from algorithm import run_optimization 

st.set_page_config(
    page_title="SA-LNS - Tân Sơn Nhất",
    layout="wide"
)

st.title("Tối ưu hóa thứ tự khởi hành tại CHKQT Tân Sơn Nhất")
st.write("Mô phỏng thuật toán SA-LNS")

# 1. Nhập dữ liệu
st.header("1. Dữ liệu chuyến bay")

uploaded_file = st.file_uploader(
    "Tải lên file Excel dữ liệu chuyến bay",
    type=["xlsx", "xls"]
)

# 2. Cấu hình thuật toán
st.header("2. Cấu hình thuật toán")

col1, col2 = st.columns(2)

with col1:
    num_runs = st.number_input(
        "Số lần chạy lặp lại SA-LNS",
        min_value=1,
        max_value=100,
        value=10
    )

with col2:
    is_peak_hour = st.checkbox(
        "Chế độ Giờ cao điểm (J=1)", 
        value=True,
        help="Đánh dấu nếu đây là khung giờ cao điểm để thuật toán thay đổi trọng số ưu tiên."
    )

# 3. Chạy thuật toán
if uploaded_file is not None:
    try:
        # Đọc dữ liệu từ file upload
        df = pd.read_excel(uploaded_file)

        st.subheader("Dữ liệu đầu vào")
        st.dataframe(df, use_container_width=True)

        if st.button("Chạy thuật toán SA-LNS"):
            with st.spinner("Hệ thống đang tiến hành tối ưu hóa, vui lòng đợi..."):
                
                # Gọi trực tiếp hàm run_optimization đã được viết sẵn trong algorithm_2.py
                # Hàm này tự động parse DataFrame thành mảng Flight và chạy thuật toán
                results = run_optimization(df, is_peak_hour=is_peak_hour, num_runs=num_runs)

            st.success("Hoàn thành tối ưu hóa!")

            # Sử dụng Tabs của Streamlit để hiển thị 4 bảng kết quả trả về từ thuật toán
            st.subheader("Bảng kết quả các phương án")
            tab1, tab2, tab3, tab4 = st.tabs([
                "PA1: SALNS Tối ưu", 
                "PA1: Greedy (Baseline)", 
                "PA2: SALNS Tối ưu (Ưu tiên Arrival)", 
                "PA2: Greedy (Ưu tiên Arrival)"
            ])
            
            with tab1:
                st.write("**Phương án 1 (Tối ưu SA-LNS)**: Tối ưu tổng chi phí phạt của cả Departure và Arrival.")
                st.dataframe(results["PA1_SALNS_Toi_Uu"], use_container_width=True)
                
            with tab2:
                st.write("**Phương án 1 (Khởi tạo Greedy)**: Xếp lịch tham lam tuần tự.")
                st.dataframe(results["PA1_Greedy_Baseline"], use_container_width=True)
                
            with tab3:
                st.write("**Phương án 2 (Tối ưu SA-LNS)**: Phạt cực lớn đối với Arrival (phi = 1000).")
                st.dataframe(results["PA2_SALNS_Toi_Uu"], use_container_width=True)
                
            with tab4:
                st.write("**Phương án 2 (Khởi tạo Greedy)**: Xếp lịch tham lam tuần tự ưu tiên Arrival.")
                st.dataframe(results["PA2_Greedy_Baseline"], use_container_width=True)

    except Exception as e:
        st.error(f"Đã xảy ra lỗi trong quá trình đọc file hoặc chạy thuật toán: {e}")
