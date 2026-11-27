import secrets
import time

from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from rooms.models import BookingRequest


class DemoPaymentForm(forms.Form):
    method = forms.ChoiceField(
        label="Hình thức thanh toán",
        choices=(
            ("momo", "Ví MoMo"),
            ("zalopay", "Ví ZaloPay"),
            ("card", "Thẻ Visa / Mastercard"),
        ),
        widget=forms.RadioSelect,
    )


RESULTS = {
    "success": "Thanh toán mô phỏng thành công",
    "failed": "Thanh toán mô phỏng thất bại",
    "expired": "Phiên thanh toán mô phỏng đã hết hạn",
}


@login_required
@require_http_methods(["GET", "POST"])
def payment_demo(request, pk):
    # Chỉ dùng khi phát triển local.
    if not settings.DEBUG:
        raise Http404

    booking = get_object_or_404(
        BookingRequest.objects.select_related("room_type"),
        pk=pk,
        customer=request.user,
    )

    if booking.status not in ("pending", "confirmed"):
        raise Http404

    attempt = request.session.get("payment_demo")

    if attempt and (
        attempt.get("booking_id") != booking.pk
        or attempt.get("user_id") != request.user.pk
    ):
        attempt = None

    # Hạn phiên được kiểm tra tại server.
    if attempt and attempt["status"] == "pending":
        if time.time() >= attempt["expires_at"]:
            attempt["status"] = "expired"
            request.session["payment_demo"] = attempt

    form = DemoPaymentForm()
    error = ""

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "start":
            form = DemoPaymentForm(request.POST)

            if form.is_valid():
                method = form.cleaned_data["method"]

                request.session["payment_demo"] = {
                    "booking_id": booking.pk,
                    "user_id": request.user.pk,
                    "token": secrets.token_urlsafe(24),
                    "method": method,
                    "method_label": dict(
                        form.fields["method"].choices
                    )[method],
                    # Lấy tiền từ database, không nhận từ trình duyệt.
                    "amount": str(booking.total_price),
                    "expires_at": time.time() + 15 * 60,
                    "status": "pending",
                }

                return redirect(
                    "website:payment_demo",
                    pk=booking.pk,
                )

        elif action == "simulate":
            valid_token = (
                attempt
                and secrets.compare_digest(
                    request.POST.get("token", ""),
                    attempt["token"],
                )
            )

            if not valid_token:
                error = (
                    "Phiên demo không hợp lệ. "
                    "Hãy mở lại từ đơn của bạn."
                )

            elif attempt["status"] == "pending":
                outcome = request.POST.get("outcome")

                if outcome in RESULTS:
                    attempt["status"] = outcome
                    request.session["payment_demo"] = attempt

                    return redirect(
                        "website:payment_demo",
                        pk=booking.pk,
                    )

                error = "Kết quả thử nghiệm không hợp lệ."

            else:
                # Gửi lại không thay đổi kết quả đã kết thúc.
                return redirect(
                    "website:payment_demo",
                    pk=booking.pk,
                )

        elif action == "reset":
            request.session.pop("payment_demo", None)

            return redirect(
                "website:payment_demo",
                pk=booking.pk,
            )

        else:
            error = "Thao tác không hợp lệ."

    remaining_seconds = 0
    result_title = ""

    if attempt:
        remaining_seconds = max(
            0,
            int(attempt["expires_at"] - time.time()),
        )
        result_title = RESULTS.get(attempt["status"], "")

    return render(
        request,
        "website/payment_demo.html",
        {
            "booking": booking,
            "form": form,
            "attempt": attempt,
            "result_title": result_title,
            "remaining_seconds": remaining_seconds,
            "nights": (
                booking.check_out - booking.check_in
            ).days,
            "error": error,
        },
    )