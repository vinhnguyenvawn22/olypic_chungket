# UNETI15 · AI04 — Lớp học thông minh

Ứng dụng React 3D + FastAPI nhận năm tín hiệu cảm biến, dự đoán phòng có người/phòng trống và đưa ra khuyến nghị kiểm tra thiết bị điện.

**Thành viên:** Nguyễn Thị Hải Yến, Doãn Hoài Nam, Nguyễn Văn Vinh.

## 1. Cài đặt và chạy

**Môi trường:** Windows, Python 3.11, Node.js 22 và npm. Thư viện Python trong `requirements.txt`; phiên bản frontend được khóa tại `frontend/package-lock.json`.

Mở PowerShell tại thư mục gốc dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
.\start.ps1
```

Mở **http://127.0.0.1:8000**. Script tự cài thư viện frontend nếu cần, build giao diện và chạy server. Dừng bằng **Ctrl+C**. Những lần sau chỉ cần kích hoạt `.venv` và chạy `.\start.ps1`.

- Đổi cổng: `.\start.ps1 -Port 8001`.
- Nếu PowerShell chặn script: chạy `Set-ExecutionPolicy -Scope Process Bypass`, rồi thực hiện lại trong cùng cửa sổ.
- Cần Internet khi cài thư viện lần đầu; mô hình suy luận cục bộ trên CPU.

## 2. Chạy dự đoán

**Trên giao diện:** chọn **Bắt đầu khám phá → Hướng dẫn nhanh**. Mở **Cảm biến**, nhập năm giá trị rồi nhấn **Phân tích mẫu**. Có thể tải `outputs/AI04/demo_sensors.csv` tại mục **Dữ liệu CSV** và bật so sánh hai mô hình trong thẻ kết quả AI.

**Qua API:** giữ server đang chạy, mở PowerShell thứ hai tại thư mục dự án:

```powershell
$predictionBody = '{"model_id":"uneti15","compare":true,"samples":[{"date":"2015-02-04 17:51:00","Temperature":23.18,"Humidity":27.272,"Light":426,"CO2":721.25,"HumidityRatio":0.00479298817650529}]}'
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/api/predict" -ContentType "application/json" -Body $predictionBody | ConvertTo-Json -Depth 8
```

Kết quả nằm trong `rows[0].results`: `label` là trạng thái (0 = trống, 1 = có người), `probability` là P(có người), `count` là số mẫu xác suất thấp liên tiếp, `alert` là khuyến nghị kiểm tra. `compare: true` trả kết quả của cả hai mô hình.

Kiểm tra **http://127.0.0.1:8000/api/health**: `models_ready` phải bằng **2**. Tài liệu API: **http://127.0.0.1:8000/docs**.

## 3. Nguồn và phiên bản mô hình

Ứng dụng nạp đúng hai mô hình đã huấn luyện; khi chạy demo chỉ thực hiện suy luận.

| Mô hình | Nguồn | Tệp trọng số | Định danh bản nộp |
| --- | --- | --- | --- |
| Logistic BTC | Mã baseline BTC: [AI04/train.py](AI04/train.py) | `outputs/AI04/model.joblib` | `dbc2a9c1c07f` |
| Logistic UNETI15 — mặc định | Đội cải tiến trong [src/01_EDA.ipynb](src/01_EDA.ipynb) | `model/logistic_optimized.joblib` | `d63a9b0a5ef8` |

- **Phiên bản thư viện mô hình:** scikit-learn **1.6.1**; seed **2026**. Hai mô hình được huấn luyện trên 8.143 mẫu `datatraining.txt`.
- **Cấu hình UNETI15:** PolynomialFeatures bậc 2, Logistic Regression với `C=0.3`, `class_weight="balanced"`. Tên `poly=1` trong nghiên cứu nghĩa là bật đa thức bậc 2.
- Định danh trên là **12 ký tự đầu SHA-256** của tệp trọng số. Hash đầy đủ và môi trường thực nghiệm có trong [notebook_run_summary.json](results/notebook_run_summary.json); cấu hình mô hình có trong [metadata](model/logistic_optimized_metadata.json).

## 4. Dữ liệu, kết quả và kiểm tra

Dữ liệu **UCI Occupancy Detection**, được BTC cung cấp: `data/AI04/datatraining.txt` dùng huấn luyện, `data/AI04/datatest.txt` gồm 2.665 mẫu dùng xác thực. Năm đầu vào: `Temperature`, `Humidity`, `Light`, `CO2`, `HumidityRatio`; nhãn `Occupancy`. ID, thời gian và nhãn không đưa vào mô hình. Thời gian chỉ phục vụ xét chuỗi khuyến nghị; `datatest2.txt` nằm ngoài phạm vi nghiên cứu.

- Phân tích và thực nghiệm: [src/01_EDA.ipynb](src/01_EDA.ipynb).
- Bảng so sánh, phân tích lỗi và biểu đồ: [results/README.md](results/README.md).
- Slide nộp: [slides.pdf](slides.pdf); bản chỉnh sửa: [slides.pptx](slides.pptx).

Kiểm tra API và suy luận hai mô hình:

```powershell
python -m pytest backend/test_api.py -q
```

**Tệp cần bổ sung để chạy lại toàn bộ nghiên cứu/kiểm thử:** `src/research_charts.py` được notebook import và `docs/model-integrity-before-energy.json` được bài kiểm thử tính toàn vẹn sử dụng. Hai tệp này hiện thiếu trong thư mục dự án; demo và bài kiểm tra API ở trên chạy độc lập với chúng.

## 5. Phạm vi và nguồn tham khảo

Khuyến nghị xuất hiện khi **P(có người) <20% trong ít nhất ba mẫu liên tiếp**; chuỗi bắt đầu lại nếu thời gian không tăng hoặc gián đoạn >120 giây. Người dùng cần kiểm tra thực tế trước khi xử lý thiết bị. Đây là nguyên mẫu dùng dữ liệu phòng làm việc, chưa được xác thực tại lớp học UNETI; chưa điều khiển điện hay đo mức tiết kiệm kWh.

Nguồn kế thừa: [UCI Occupancy Detection](https://archive.ics.uci.edu/dataset/357/occupancy+detection), **baseline BTC** và các thư viện trong requirements/lockfile. Phần đội thực hiện: cải tiến Logistic, so sánh thực nghiệm, phân tích lỗi, logic khuyến nghị và ứng dụng minh họa. Công cụ AI hỗ trợ lập trình, biên tập: **OpenAI Codex**.

## Demo trực tuyến

Danh sách tệp cần đưa lên GitHub và cách triển khai React + FastAPI trên Render: [DEPLOY_RENDER.md](DEPLOY_RENDER.md). Cấu hình dịch vụ nằm trong `render.yaml`; thư viện chạy demo được ghim tại `requirements-render.txt`.
# olypic_chungket
