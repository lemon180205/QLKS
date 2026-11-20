from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User

class HotelUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Thông tin khách sạn", {"fields": ("phone",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Thông tin khách sạn", {"fields": ("email", "first_name", "last_name", "phone")}),
    )
    list_display = UserAdmin.list_display + ("phone",)


admin.site.register(User, HotelUserAdmin)
admin.site.site_header = "Hệ thống quản lý khách sạn"
admin.site.site_title = "Quản lý khách sạn"
admin.site.index_title = "Trang quản trị"