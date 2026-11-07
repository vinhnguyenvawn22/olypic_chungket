# Đưa demo UNETI15 lên Render

Frontend và API chạy chung một Python Web Service. Hai mô hình chạy trên server; trình duyệt gửi yêu cầu tới `/api` trên cùng tên miền.

## Tệp cần đưa lên GitHub

Giữ nguyên đường dẫn tương đối như trong dự án:

```text
render.yaml
.python-version
.node-version
.gitignore
requirements-render.txt
backend/                         # mã Python; bỏ __pycache__
frontend/src/
frontend/public/
frontend/index.html
frontend/package.json
frontend/package-lock.json
frontend/tsconfig.json
frontend/vite.config.ts
model/logistic_optimized.joblib
model/logistic_optimized_metadata.json
model/ai04_app_config.json
outputs/AI04/model.joblib
outputs/AI04/metrics.json
outputs/AI04/demo_sensors.csv
data/AI04/datatraining.txt
```

`datatraining.txt` phục vụ các nút tình huống có sẵn. Render chỉ suy luận bằng hai mô hình đã lưu, không chạy notebook hoặc huấn luyện lại. JSON đi kèm phục vụ thông tin mô hình; CSV mẫu giúp thử upload.

Không cần đưa `frontend/node_modules/`, `frontend/dist/`, môi trường Python, cache, notebook, results, slides, đề thi, app Streamlit cũ, Random Forest hoặc hai tệp dữ liệu đánh giá lên repository chỉ dùng để chạy demo. Giữ các tệp bài nộp tại thư mục dự án gốc.

## Tạo dịch vụ

1. Đưa các tệp trên vào repository GitHub, giữ nguyên cấu trúc thư mục; không nén chúng thành một tệp ZIP trong repository.
2. Đăng nhập Render, chọn **New → Blueprint**, kết nối GitHub và chọn repository chứa app.
3. Render đọc `render.yaml`. Kiểm tra dịch vụ `uneti15-smart-classroom`, gói **Free**, rồi triển khai.
4. Khi trạng thái là **Live**, mở URL `https://…onrender.com` do Render cấp.

Nếu tạo bằng **New → Web Service** thay vì Blueprint, chọn Python 3, để Root Directory trống, và dùng:

```text
Build Command:
python -m pip install -r requirements-render.txt && npm --prefix frontend ci --include=dev && npm --prefix frontend run build

Start Command:
python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT --workers 1

Health Check Path:
/api/health
```

Hai tệp `.python-version` và `.node-version` chọn phiên bản runtime; không để biến môi trường PYTHON_VERSION/NODE_VERSION cũ ghi đè chúng. Gói Free trong Blueprint được khai báo rõ để tránh chọn nhầm gói trả phí mặc định.

## Kiểm tra trước khi gửi link cho BTC

- Mở `/api/health`: `status` là `ok`, `models_ready` bằng **2**, `sklearn_version` là **1.6.1**. Health endpoint báo tình trạng kết nối; cần đọc `models_ready` để xác nhận đủ mô hình.
- Mở ứng dụng bằng cửa sổ ẩn danh; nhập cảm biến, phân tích, bật so sánh hai mô hình và nạp tình huống CSV.
- Thử trên điện thoại hoặc máy khác; kiểm tra phòng 3D và chế độ 2D.
- Gửi URL do Render cấp sau khi các bước trên đạt. Máy cá nhân có thể tắt sau khi deploy thành công.

Gói Free ngủ sau 15 phút không có truy cập; mở link sẽ tự đánh thức dịch vụ và thường phải chờ khoảng một phút. Tệp CSV người dùng tải lên được xử lý trong bộ nhớ; lịch sử/xác nhận của từng người nằm trong phiên trình duyệt, không có cơ sở dữ liệu lưu lâu dài.

Nguồn: [Render FastAPI](https://render.com/docs/deploy-fastapi), [Blueprint](https://render.com/docs/blueprint-spec), [Python](https://render.com/docs/python-version), [Node.js](https://render.com/docs/node-version), [giới hạn gói Free](https://render.com/docs/free).
