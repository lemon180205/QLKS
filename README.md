# Hệ thống quản lý khách sạn và homestay

Đồ án môn học được phát triển bằng Python và Django, sử dụng PostgreSQL.

## Yêu cầu

- Windows và PowerShell
- Python 3.10 trở lên, có lệnh `py`
- Git

## Cài đặt lần đầu

Mở PowerShell và chạy:

```powershell
git clone https://github.com/lemon180205/QLKS.git
cd QLKS
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Tạo file `.env` cùng cấp với `manage.py` từ tệp mẫu:

```powershell
Copy-Item .env.example .env
```

Mở `.env` và thay các giá trị mẫu bằng thông tin PostgreSQL, SMTP và tài khoản MoMo sandbox của bạn. Với Gmail, dùng App Password thay cho mật khẩu đăng nhập. Không gửi mật khẩu/API key qua chat hoặc commit `.env`; tệp này đã được `.gitignore` loại trừ. Chỉ cần cấu hình SMTP nếu muốn gửi email thật. MoMo sandbox cần URL HTTPS công khai để nhận IPN; URL localhost không thể nhận xác nhận giao dịch từ MoMo.

Sau đó chạy:

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Nếu PowerShell chặn kích hoạt môi trường ảo, chỉ cho phép script trong cửa sổ hiện tại rồi kích hoạt lại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

Hoặc không cần kích hoạt môi trường ảo; thay `python` bằng `.\venv\Scripts\python.exe` trong các lệnh Django và pip, ví dụ:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py createsuperuser
.\venv\Scripts\python.exe manage.py runserver
```

Khi tạo superuser, nhập tên đăng nhập, email (nếu được hỏi) và mật khẩu hai lần. Ký tự mật khẩu sẽ không hiển thị khi gõ. Mỗi thành viên cần tự tạo tài khoản quản trị trên máy của mình.

Để tạo tài khoản lễ tân, superuser vào **Users → Add user**, bật **Staff status** và chỉ cấp quyền cần thiết: xem/thêm/sửa **Booking requests**, xem **Rooms** và **Room types**, và xem **Users** nếu cần gắn đặt phòng với tài khoản khách. Cấp quyền xem **Booking payments** nếu lễ tân cần tra cứu giao dịch. Khách tự đăng ký trên website; không bật quyền Staff cho tài khoản khách.

Sau khi chạy server, giữ cửa sổ PowerShell mở và truy cập:

- Website: http://127.0.0.1:8000/
- Trang quản trị: http://127.0.0.1:8000/admin/

## Dashboard và quản lý khách sạn

Trang `/admin/` là dashboard quản trị, có thanh điều hướng bên trái và thống kê tổng số phòng, phòng thường, phòng VIP, tình trạng phòng, số tầng và dịch vụ. Dùng mũi tên ở đầu mỗi nhóm trong thanh bên để thu gọn hoặc mở các tiện ích; nhóm đang mở hiển thị những tác vụ có thể truy cập. Đăng nhập bằng tài khoản superuser để sử dụng các tác vụ:

- **Phòng**: thêm và cập nhật số phòng, tầng, loại phòng và trạng thái.
- **Loại phòng**: quản lý hạng thường/VIP, sức chứa, giá mỗi đêm và ảnh.
- **Dịch vụ**: quản lý dịch vụ ăn uống, giặt ủi hoặc dịch vụ khác; cập nhật giá và trạng thái phục vụ.
- **Yêu cầu đặt phòng**: xem thông tin khách, lịch lưu trú và tổng giá dự kiến; cập nhật trạng thái chờ xác nhận, đã xác nhận, đang lưu trú, đã trả phòng hoặc đã hủy.
- **Đặt hộ qua điện thoại**: nhân viên mở Yêu cầu đặt phòng và thêm hồ sơ bằng tên/số điện thoại; email và liên kết tài khoản khách không bắt buộc. Có thể lọc theo trạng thái, ngày và loại phòng.
- **Tài khoản khách**: không bắt buộc để tìm phòng hoặc gửi yêu cầu đặt phòng. Khách có tài khoản có thể đăng nhập để xem lịch đặt, theo dõi thanh toán và hủy yêu cầu chưa thanh toán.
- **MoMo sandbox**: khách thanh toán trong tài khoản. Chỉ IPN hợp lệ có chữ ký mới cập nhật thanh toán và xác nhận đặt phòng; trang chuyển hướng từ MoMo không tự được coi là bằng chứng thanh toán.
- **Email SMTP**: hệ thống gửi email khi nhận yêu cầu, khi thanh toán thành công và khi lễ tân tạo/cập nhật đặt phòng. Nếu gửi thất bại, đặt phòng vẫn được lưu và người dùng được thông báo; kiểm tra log và cấu hình SMTP.

Lần đầu chạy `python manage.py migrate`, hệ thống tạo sẵn 5 loại phòng và 50 phòng (30 phòng thường, 20 phòng VIP), cùng một số dịch vụ mẫu. Migration chỉ tạo dữ liệu mẫu một lần; các thay đổi sau đó được lưu trong database của máy.

Khách có thể tìm phòng theo ngày và số khách theo giao diện đặt phòng lấy cảm hứng từ các trang OTA, xem dịch vụ đang mở, rồi gửi yêu cầu đặt phòng trên website mà không cần đăng nhập. Biểu mẫu yêu cầu tên, email và số điện thoại để lễ tân liên hệ; sau khi gửi, khách nhận mã đặt phòng và có thể đưa mã cho lễ tân khi đến để xác nhận thông tin. Yêu cầu ở trạng thái chờ xác nhận, không đồng nghĩa với xác nhận lưu trú hay thanh toán thành công. Khách có tài khoản có thể đăng nhập để theo dõi đặt phòng và thanh toán; nhân viên có thể tiếp nhận đặt phòng qua điện thoại trong Admin. Phòng trong yêu cầu đang hoạt động được tính vào lượng phòng còn trống.

## Chạy lại dự án

Sau khi đã tạo `.env` và thiết lập PostgreSQL, mở PowerShell tại thư mục `QLKS`, kích hoạt môi trường và chạy:

```powershell
.\venv\Scripts\Activate.ps1
python manage.py migrate
python manage.py runserver
```

Không cần tạo lại môi trường ảo hoặc superuser mỗi lần chạy.

## Cập nhật code mới từ GitHub

Nếu server đang chạy, nhấn `Ctrl+C` để dừng. Tại thư mục dự án, kiểm tra thay đổi cục bộ rồi lấy code mới:

```powershell
git status
git pull origin main
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Nếu `git status` cho thấy có thay đổi chưa lưu, hãy commit hoặc stash chúng trước khi pull để tránh xung đột. Không chạy `git pull` khi chưa hiểu các thay đổi cục bộ.

## Đóng góp code lên GitHub

Tạo nhánh riêng cho mỗi công việc:

```powershell
git switch main
git pull origin main
git switch -c ten-thanh-vien/ten-chuc-nang
```

Sau khi hoàn thành thay đổi, kiểm tra và đẩy nhánh lên GitHub:

```powershell
git status
git add .
git commit -m "Mo ta thay doi"
git push -u origin ten-thanh-vien/ten-chuc-nang
```

Tạo Pull Request trên GitHub để thành viên khác xem xét và gộp vào `main`. Sau khi Pull Request được gộp, cập nhật máy của bạn:

```powershell
git switch main
git pull origin main
python -m pip install -r requirements.txt
python manage.py migrate
```

Nếu thay đổi model, tạo các tệp migration bằng `python manage.py makemigrations` và đưa các tệp migration đó lên GitHub cùng với code. Thành viên khác chạy `python manage.py migrate` sau khi cập nhật code.

## Lệnh thường dùng

Chạy kiểm tra cấu hình và bài kiểm thử:

```powershell
python manage.py check
python manage.py test
```

Đổi mật khẩu tài khoản quản trị:

```powershell
python manage.py changepassword ten_dang_nhap
```

## Cơ sở dữ liệu và môi trường

- `venv/` là môi trường Python cục bộ; không đưa thư mục này lên GitHub.
- Dự án dùng PostgreSQL. Cấu hình database, SMTP, MoMo và thiết lập bảo mật được đọc từ file `.env` ở thư mục gốc.
- `.env` chứa thông tin riêng của từng máy, đã được `.gitignore` loại trừ; mỗi thành viên tự tạo file này và cấu hình database riêng.
- Tài khoản và dữ liệu PostgreSQL không được đồng bộ qua GitHub.
- Các dependency của dự án được khai báo trong `requirements.txt`.
- Nếu gặp `ModuleNotFoundError: No module named 'django'`, kích hoạt đúng `venv` rồi chạy `python -m pip install -r requirements.txt`; kiểm tra interpreter bằng `python -m pip show Django`.
- Không chạy đồng thời lệnh trong `venv` và `.venv`; luôn dùng cùng một môi trường cho cả `pip` và `manage.py`.
- Trước khi triển khai thật, đặt `DJANGO_DEBUG=false`, tạo `DJANGO_SECRET_KEY` ngẫu nhiên đủ dài, đặt `DJANGO_ALLOWED_HOSTS` đúng domain và cấu hình HTTPS/SMTP/MoMo production. Không dùng các giá trị mẫu trong `.env.example` ở production.