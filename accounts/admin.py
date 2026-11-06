from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User

admin.site.register(User, UserAdmin)
admin.site.site_header = "Hệ thống quản lý khách sạn"
admin.site.site_title = "Quản lý khách sạn"
admin.site.index_title = "Trang quản trị"