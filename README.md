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

Để tạo tài khoản lễ tân, superuser vào **Users → Add user**, bật **Staff status** và chỉ cấp quyền cần thiết: xem/thêm/sửa **Booking requests**, xem **Rooms** và **Room types**, và xem **Users** nếu cần gắn đặt phòng với tài khoản khách. Cấp quyền xem **Booking payments** và **Khoản thu tại quầy** nếu lễ tân cần tra cứu lịch sử thu. Khách tự đăng ký trên website; không bật quyền Staff cho tài khoản khách.

Sau khi chạy server, giữ cửa sổ PowerShell mở và truy cập:

- Website: http://127.0.0.1:8000/
- Trang quản trị: http://127.0.0.1:8000/admin/

## Dashboard và quản lý khách sạn

Trang `/admin/` là dashboard quản trị, có thanh điều hướng bên trái và thống kê tổng số phòng, phòng thường, phòng VIP, tình trạng phòng, số tầng và dịch vụ. Dùng mũi tên ở đầu mỗi nhóm trong thanh bên để thu gọn hoặc mở các tiện ích; nhóm đang mở hiển thị những tác vụ có thể truy cập. Đăng nhập bằng tài khoản superuser để sử dụng các tác vụ:

- **Phòng**: thêm và cập nhật số phòng, tầng, loại phòng và trạng thái.
- **Loại phòng**: quản lý hạng thường/VIP, sức chứa, giá mỗi đêm và ảnh.
- **Dịch vụ**: quản lý dịch vụ ăn uống, giặt ủi hoặc dịch vụ khác; cập nhật giá và trạng thái phục vụ.
- **Yêu cầu đặt phòng**: xem thông tin khách, lịch lưu trú và tổng giá dự kiến; cập nhật trạng thái chờ xác nhận, đã xác nhận, đang lưu trú, đã trả phòng hoặc đã hủy. Khi khách đang lưu trú, mở đơn để ghi dịch vụ phát sinh và số lượng; đơn giá được lưu theo giá dịch vụ tại lúc ghi nhận. Thao tác **Check-out** mở bảng chốt tiền gồm tiền phòng, dịch vụ, tiền đã trả MoMo và dư nợ; nếu còn nợ, chọn phương thức thu tại quầy để ghi nhận khoản thu trước khi trả phòng. Lịch sử khoản thu tại quầy chỉ xem được, không thể tạo/sửa/xóa thủ công.
- **Báo cáo doanh thu theo tháng**: mở từ danh sách Yêu cầu đặt phòng. Doanh thu tính theo thời điểm thực nhận trong múi giờ `Asia/Ho_Chi_Minh`, tách tiền phòng, dịch vụ và tổng thu. Chỉ MoMo thành công mới được tính; giao dịch thất bại/đang xử lý không cộng vào doanh thu. Báo cáo cũng liệt kê dư nợ hiện tại và giao dịch MoMo thất bại riêng để đối soát. Tiền phòng và dịch vụ được tính vào tháng thu tương ứng, kể cả khi được thanh toán ở các tháng khác nhau. Với giao dịch thất bại cũ chưa lưu thời điểm thất bại, báo cáo dùng thời điểm tạo giao dịch làm mốc.
- **Đặt hộ qua điện thoại**: nhân viên mở Yêu cầu đặt phòng và thêm hồ sơ bằng tên/số điện thoại; email và liên kết tài khoản khách không bắt buộc. Có thể lọc theo trạng thái, ngày và loại phòng.
- **Tài khoản khách**: không bắt buộc để tìm phòng hoặc gửi yêu cầu đặt phòng. Khách có tài khoản có thể đăng nhập để xem lịch đặt, theo dõi thanh toán và hủy yêu cầu chưa thanh toán.
- **MoMo sandbox**: khách thanh toán trong tài khoản. Chỉ IPN hợp lệ có chữ ký mới cập nhật thanh toán và xác nhận đặt phòng; trang chuyển hướng từ MoMo không tự được coi là bằng chứng thanh toán.
- **Email SMTP**: hệ thống gửi email khi nhận yêu cầu, khi thanh toán thành công và khi lễ tân tạo/cập nhật đặt phòng. Nếu gửi thất bại, đặt phòng vẫn được lưu và người dùng được thông báo; kiểm tra log và cấu hình SMTP.

Lần đầu chạy `python manage.py migrate`, hệ thống tạo sẵn 5 loại phòng và 50 phòng (30 phòng thường, 20 phòng VIP), cùng một số dịch vụ mẫu. Migration chỉ tạo dữ liệu mẫu một lần; các thay đổi sau đó được lưu trong database của máy.

Khách có thể tìm phòng theo ngày và số khách theo giao diện đặt phòng lấy cảm hứng từ các trang OTA, xem dịch vụ đang mở, rồi gửi yêu cầu đặt phòng trên website mà không cần đăng nhập. Biểu mẫu yêu cầu tên, email và số điện thoại để lễ tân liên hệ; sau khi gửi, khách nhận mã đặt phòng và có thể đưa mã cho lễ tân khi đến để xác nhận thông tin. Yêu cầu ở trạng thái chờ xác nhận, không đồng nghĩa với xác nhận lưu trú hay thanh toán thành công. Khách có tài khoản có thể đăng nhập để theo dõi đặt phòng và thanh toán; nhân viên có thể tiếp nhận đặt phòng qua điện thoại trong Admin. Đơn chờ xác nhận không tự giữ chỗ; đơn đã xác nhận hoặc đang lưu trú giữ chỗ, còn đơn chờ xác nhận chỉ tạm giữ khi thanh toán MoMo đang xử lý. Phòng đang dọn không nhận khách trong ngày nhưng được tính cho ngày nhận phòng tương lai; phòng bảo trì luôn bị loại trừ đến khi được chuyển trạng thái. Số phòng trống được tính theo mức đặt phòng đồng thời cao nhất trong toàn bộ khoảng ngày, không cộng các đặt phòng không trùng đêm.

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

## Quy trình kiểm thử website

Thực hiện quy trình dưới đây trên database phát triển hoặc database kiểm thử riêng, không dùng dữ liệu khách hàng thật. Repository không có sẵn tài khoản/mật khẩu dùng chung; mỗi người tạo tài khoản trên máy của mình và không ghi mật khẩu, khóa API vào README hoặc Git.

### Chuẩn bị tài khoản

Tạo và dùng riêng các vai trò sau:

- **Quản trị viên (superuser)**: tạo bằng `python manage.py createsuperuser`; dùng để cấu hình dữ liệu và tạo tài khoản nhân viên.
- **Lễ tân (staff)**: tạo trong Admin tại **Users → Add user**, bật **Staff status** và chỉ cấp quyền cần thiết cho đặt phòng, phòng, loại phòng và các dữ liệu liên quan. Dùng tài khoản này để kiểm tra các thao tác nghiệp vụ với quyền nhân viên, thay vì dùng superuser.
- **Khách hàng**: đăng ký từ website tại mục đăng ký. Dùng tài khoản này để kiểm tra đăng nhập, đặt phòng và xem các đặt phòng của chính khách.

Có thể mở website bằng cửa sổ thường, Admin bằng cửa sổ khác và tài khoản khách bằng cửa sổ riêng tư để tránh nhầm phiên đăng nhập. Tài khoản khách không được bật **Staff status**.

### Các bước kiểm thử thủ công

1. **Kiểm tra website công khai**: mở trang chủ, tìm loại phòng theo ngày/số khách, xem chi tiết phòng và dịch vụ. Thử ngày trả phòng trước ngày nhận phòng để xác nhận biểu mẫu báo lỗi phù hợp.
2. **Kiểm tra đặt phòng**: gửi một yêu cầu khi chưa đăng nhập và một yêu cầu khi đã đăng nhập bằng tài khoản khách. Xác nhận trang kết quả hiển thị mã đặt phòng; đơn mới là **chờ xác nhận**, chưa phải xác nhận lưu trú hay thanh toán thành công. Đăng nhập tài khoản khách và kiểm tra chỉ thấy được đặt phòng của tài khoản đó.
3. **Kiểm tra xử lý tại Admin**: đăng nhập bằng lễ tân, mở **Yêu cầu đặt phòng**, tìm yêu cầu vừa tạo và xác nhận đơn. Chọn ngày nhận phòng là hôm nay để kiểm thử check-in; xác nhận đơn chưa phù hợp trạng thái/ngày hoặc phòng không sẵn sàng thì không thể check-in. Sau check-in, thêm dịch vụ và số lượng vào đơn; kiểm tra đơn giá được ghi nhận tại thời điểm sử dụng.
4. **Kiểm tra check-out và thu tiền**: mở thao tác **Check-out**, đối chiếu tiền phòng, tiền dịch vụ, khoản MoMo đã thanh toán và số còn phải thu. Nếu còn dư nợ, chọn phương thức thu tại quầy và xác nhận; kiểm tra lịch sử khoản thu có số tiền, phương thức, thời gian và nhân viên thực hiện. Thử gửi lại thao tác check-out để xác nhận không thu tiền lần thứ hai.
5. **Kiểm tra báo cáo doanh thu**: mở báo cáo tháng từ danh sách **Yêu cầu đặt phòng**, chọn tháng có khoản thu. Đối chiếu riêng tiền phòng, dịch vụ và tổng thu với các khoản thực nhận. Giao dịch MoMo thất bại/đang xử lý không được tính là doanh thu; khoản còn nợ và giao dịch thất bại hiển thị riêng. Nếu kiểm tra phân bổ giữa các tháng, thu tiền phòng trong một tháng và dịch vụ trong tháng khác rồi xem từng báo cáo.
6. **Kiểm tra trạng thái phòng**: sau check-out, phòng chuyển sang **Đang dọn**. Xác nhận phòng không được tính sẵn sàng cho khách đến trong ngày; sau khi lễ tân xác nhận dọn xong, phòng trở lại trạng thái sẵn sàng. Phòng bảo trì không xuất hiện như phòng trống.

Ghi lại mã đặt phòng và số liệu cần đối chiếu trong ghi chú kiểm thử cục bộ; không đưa thông tin cá nhân hoặc thông tin đăng nhập lên GitHub. Khi cần chạy kiểm thử tự động, tại thư mục dự án chạy:

```powershell
python manage.py check
python manage.py test
```

### Kiểm thử MoMo và email

Thanh toán MoMo cần thông tin **sandbox** riêng trong `.env`. MoMo phải gọi được địa chỉ IPN qua HTTPS công khai; `localhost` không nhận được callback từ MoMo. Vì vậy, ở môi trường local có thể kiểm thử phần còn lại của luồng và thu tiền tại quầy; chỉ kiểm thử trọn vẹn callback MoMo trên môi trường thử nghiệm có HTTPS và URL IPN truy cập được. Không dùng khóa MoMo production để kiểm thử. Email thật cũng chỉ gửi được khi SMTP đã cấu hình; nếu chưa cấu hình, kiểm tra các chức năng không phụ thuộc email trước.

Quy trình này là kiểm thử trước triển khai, không thay thế bước triển khai và nghiệm thu trên môi trường thực tế. Chỉ chuyển sang triển khai khi các luồng cần thiết đã được kiểm thử trên môi trường thử nghiệm và dữ liệu đối chiếu đạt yêu cầu.