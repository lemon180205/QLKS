from django import forms
from django.utils import timezone

from rooms.availability import get_available_room_count
from rooms.models import BookingRequest


class RoomSearchForm(forms.Form):
    check_in = forms.DateField(
        label="Ngày nhận phòng",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    check_out = forms.DateField(
        label="Ngày trả phòng",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    guest_count = forms.IntegerField(
        label="Số khách",
        required=False,
        min_value=1,
        initial=1,
    )

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get("check_in")
        check_out = cleaned_data.get("check_out")

        if bool(check_in) != bool(check_out):
            raise forms.ValidationError(
                "Vui lòng chọn cả ngày nhận phòng và ngày trả phòng."
            )
        if check_in and check_out:
            if check_in < timezone.localdate():
                self.add_error("check_in", "Ngày nhận phòng không thể ở quá khứ.")
            if check_out <= check_in:
                self.add_error(
                    "check_out",
                    "Ngày trả phòng phải sau ngày nhận phòng.",
                )
        return cleaned_data


class BookingRequestForm(forms.ModelForm):
    class Meta:
        model = BookingRequest
        fields = (
            "guest_name",
            "email",
            "phone",
            "check_in",
            "check_out",
            "guest_count",
        )
        widgets = {
            "check_in": forms.DateInput(attrs={"type": "date"}),
            "check_out": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, room_type, **kwargs):
        self.room_type = room_type
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get("check_in")
        check_out = cleaned_data.get("check_out")
        guest_count = cleaned_data.get("guest_count")

        if check_in and check_in < timezone.localdate():
            self.add_error("check_in", "Ngày nhận phòng không thể ở quá khứ.")
        if check_in and check_out and check_out <= check_in:
            self.add_error(
                "check_out",
                "Ngày trả phòng phải sau ngày nhận phòng.",
            )
        if guest_count and guest_count > self.room_type.capacity:
            self.add_error(
                "guest_count",
                f"Loại phòng này tối đa {self.room_type.capacity} khách.",
            )
        if (
            check_in
            and check_out
            and check_out > check_in
            and check_in >= timezone.localdate()
            and not (guest_count and guest_count > self.room_type.capacity)
            and get_available_room_count(self.room_type, check_in, check_out) < 1
        ):
            raise forms.ValidationError(
                "Loại phòng này hiện không còn phòng trống trong khoảng ngày đã chọn."
            )
        return cleaned_data

    def save(self, commit=True):
        booking = super().save(commit=False)
        booking.room_type = self.room_type
        booking.nightly_rate = self.room_type.price_per_night
        booking.total_price = (
            self.room_type.price_per_night
            * (booking.check_out - booking.check_in).days
        )
        if commit:
            booking.save()
        return booking
