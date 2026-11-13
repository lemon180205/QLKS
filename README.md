# Hệ thống quản lý khách sạn và homestay

Đồ án môn học được phát triển bằng Python và Django. Dự án sử dụng SQLite làm cơ sở dữ liệu mặc định.

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

Sau khi chạy server, giữ cửa sổ PowerShell mở và truy cập:

- Website: http://127.0.0.1:8000/
- Trang quản trị: http://127.0.0.1:8000/admin/

## Dashboard và quản lý khách sạn

Trang `/admin/` là dashboard quản trị, có thanh điều hướng bên trái và thống kê tổng số phòng, phòng thường, phòng VIP, tình trạng phòng, số tầng và dịch vụ. Dùng mũi tên ở đầu mỗi nhóm trong thanh bên để thu gọn hoặc mở các tiện ích; nhóm đang mở hiển thị những tác vụ có thể truy cập. Đăng nhập bằng tài khoản superuser để sử dụng các tác vụ:

- **Phòng**: thêm và cập nhật số phòng, tầng, loại phòng và trạng thái.
- **Loại phòng**: quản lý hạng thường/VIP, sức chứa, giá mỗi đêm và ảnh.
- **Dịch vụ**: quản lý dịch vụ ăn uống, giặt ủi hoặc dịch vụ khác; cập nhật giá và trạng thái phục vụ.
- **Yêu cầu đặt phòng**: xem thông tin khách, lịch lưu trú và tổng giá dự kiến; cập nhật trạng thái chờ xác nhận, đã xác nhận, đang lưu trú, đã trả phòng hoặc đã hủy.

Lần đầu chạy `python manage.py migrate`, hệ thống tạo sẵn 5 loại phòng và 50 phòng (30 phòng thường, 20 phòng VIP), cùng một số dịch vụ mẫu. Migration chỉ tạo dữ liệu mẫu một lần; các thay đổi sau đó được lưu trong database của máy.

Khách có thể tìm phòng theo ngày và số khách, xem dịch vụ đang mở, rồi gửi yêu cầu đặt phòng trên website. Yêu cầu chưa phải xác nhận đặt phòng hay thanh toán; nhân viên cần kiểm tra và xử lý trong trang Admin. Phòng trong yêu cầu đang hoạt động được tính vào lượng phòng còn trống.

## Chạy lại dự án

Mở PowerShell tại thư mục `QLKS`, kích hoạt môi trường và chạy:

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
- `db.sqlite3` chứa dữ liệu cục bộ; các tài khoản và dữ liệu trong database không được đồng bộ qua GitHub.
- Các dependency của dự án được khai báo trong `requirements.txt`.
