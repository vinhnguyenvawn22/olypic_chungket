# Kết quả nộp bài UNETI15 — AI04

Bộ kết quả chọn lọc: 8 CSV, 1 JSON tổng hợp, 7 hình PNG và README này. Mã nguồn, dữ liệu được phép, requirements, hai mô hình ứng dụng và slides.pdf là các thành phần khác của gói nộp, nằm ngoài thư mục kết quả.

## Bảng và báo cáo

| Tệp | Vai trò |
| --- | --- |
| [so_sanh_hai_mo_hinh_logistic.csv](so_sanh_hai_mo_hinh_logistic.csv) | Baseline và cải tiến trên cùng validation: Macro-F1, Recall, FER, TN/FP/FN/TP và F1 từng lớp. |
| [so_sanh_16_cau_hinh_logistic.csv](so_sanh_16_cau_hinh_logistic.csv) | Cùng 16 cấu hình Logistic trên hai quy trình CV nội bộ; bằng chứng lựa chọn. |
| [ket_qua_tung_lan_kiem_tra_cheo.csv](ket_qua_tung_lan_kiem_tra_cheo.csv) | Kết quả từng phần chia của baseline và mô hình chọn, trong cả hai quy trình; đọc cùng số mẫu. |
| [danh_gia_tung_thanh_phan_cai_tien.csv](danh_gia_tung_thanh_phan_cai_tien.csv) | Tác dụng và đánh đổi của đa thức, trọng số lớp, C. |
| [cac_mau_co_nguoi_bi_du_doan_trong.csv](cac_mau_co_nguoi_bi_du_doan_trong.csv) | Các mẫu có người bị ít nhất một mô hình nhận nhầm thành phòng trống, kèm tín hiệu và xác suất. |
| [so_sanh_cac_phuong_an_khuyen_nghi.csv](so_sanh_cac_phuong_an_khuyen_nghi.csv) | So sánh ba phương án khuyến nghị theo mẫu/đợt trên dữ liệu thật. |
| [kiem_thu_chuoi_du_lieu_gian_doan.csv](kiem_thu_chuoi_du_lieu_gian_doan.csv) | Kiểm thử gián đoạn bằng xác suất giả lập, so sánh logic gốc và gap check; không gộp vào chất lượng validation. |
| [chi_tiet_du_doan_va_khuyen_nghi.csv](chi_tiet_du_doan_va_khuyen_nghi.csv) | Một bảng chi tiết duy nhất cho toàn bộ 2.665 mẫu: cảm biến, nhãn, dự đoán, xác suất và ba cột khuyến nghị. |
| [tong_hop_ket_qua_nghien_cuu.json](tong_hop_ket_qua_nghien_cuu.json) | Kết quả tổng hợp, quy tắc lựa chọn, môi trường, hash, đối chiếu mô hình và kiểm tra hình. |

## Hình chọn đưa vào báo cáo

| Hình | Thông điệp chính | Tệp |
| --- | --- | --- |
| 01 · Phân bố trạng thái phòng | Phòng trống chiếm 78,8%; đọc thêm Macro-F1 và lỗi bỏ sót có người. | [PNG](bieu_do/01_phan_bo_trang_thai_phong.png) |
| 02 · Phân bố độ rọi | Hai lớp dùng chung biên histogram; hình giới hạn đến phân vị 99,5%, mô hình dùng dữ liệu gốc. | [PNG](bieu_do/02_phan_bo_anh_sang.png) |
| 03 · Phân bố nồng độ CO₂ | Hai lớp dùng chung biên histogram; hình giới hạn đến phân vị 99,5%, mô hình dùng dữ liệu gốc. | [PNG](bieu_do/03_phan_bo_nong_do_co2.png) |
| 07 · So sánh hai quy trình CV | Mỗi hàng là một quy trình riêng; so sánh baseline và cải tiến trong cùng hàng, cùng các phần chia dữ liệu. | [PNG](bieu_do/07_so_sanh_hai_cach_kiem_tra_mo_hinh.png) |
| 08 · Hai ma trận nhầm lẫn | Lỗi có người → phòng trống: 7 → 2; lỗi ngược lại 54 → 55. | [PNG](bieu_do/08_ma_tran_nham_lan_hai_mo_hinh.png) |
| 09 · Xác suất và khuyến nghị cả ngày | Ngày 03/02/2015 có 1 mẫu khuyến nghị khi thực tế còn người; ngưỡng khuyến nghị khác quyết định phân loại. | [PNG](bieu_do/09_xac_suat_va_khuyen_nghi_theo_thoi_gian.png) |
| 11 · Phóng to quanh khuyến nghị sai | Khoảng ±12 phút quanh 07:36:00 03/02/2015: đọc xác suất, nhãn thật và điều kiện khuyến nghị cùng thời điểm. | [PNG](bieu_do/11_phan_tich_mau_khuyen_nghi_sai.png) |

Các hình phụ vẫn có trong output notebook; chỉ bảy hình tiêu biểu được xuất ra bộ nộp. Giữ duy nhất PNG để dùng ngoại tuyến, không kèm bản SVG và danh mục HTML trùng nội dung.

## Cách đọc và tái lập

- Lớp dương là có người. FER = FN/(FN+TP); không phải tỷ lệ lỗi trên toàn bộ mẫu. Macro-F1 là trung bình F1 hai lớp.
- Cả hai mô hình dùng đúng năm cảm biến. Chọn cấu hình bằng CV bên trong datatraining.txt; so sánh cuối trên datatest.txt, không trộn hai loại kết quả.
- Validation đã từng được xem trong nghiên cứu. Dữ liệu là phòng làm việc UCI, chưa xác thực tại lớp học UNETI. Không đọc datatest2.txt.
- Khuyến nghị: P(có người) <20% trong ít nhất ba mẫu liên tiếp; gap check reset khi thời gian không tăng hoặc cách nhau >120 giây. Ba mẫu không đồng nghĩa ba phút.
- Cột btc_alert dùng baseline + logic gốc; optimized_alert dùng cải tiến + logic gốc; optimized_gap_alert dùng cải tiến + gap check. True là có khuyến nghị kiểm tra, không phải đã tắt điện.
- Đọc bảng khuyến nghị độc lập với bảng phân loại; giảm FN không bảo đảm số mẫu khuyến nghị sai giảm. Giữ bước kiểm tra thực tế trước hành động.
- Môi trường và lệnh chạy demo nằm trong [README gốc](../README.md). Notebook `src/Train.ipynb` tái lập trong bộ nhớ và chỉ xuất bộ kết quả chọn lọc; module biểu đồ nằm trong `src/research_charts.py`.
- Kiểm thử chi tiết, thống kê EDA phụ và kết quả search đầy đủ có trong notebook. Các cột thời gian fit được giữ ở output nghiên cứu, không dùng làm chỉ số chất lượng của bộ nộp.


## Nghiên cứu cải tiến hiện tại

Xem thư mục cai_tien và notebook Cai_tien_mo_hinh.ipynb. Các bảng gốc và bảng mới dùng phép chia khác nhau. Đối chiếu số mẫu và tên quy trình trước khi so sánh.
