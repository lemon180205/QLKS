import hashlib
import hmac
import json
import logging
from http.client import HTTPException
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


class MomoConfigurationError(Exception):
    pass


class MomoGatewayError(Exception):
    pass


def _secret_key():
    if not settings.MOMO_SECRET_KEY:
        raise MomoConfigurationError("MoMo chưa được cấu hình MOMO_SECRET_KEY.")
    return settings.MOMO_SECRET_KEY


def _signature(data, fields):
    if not settings.MOMO_ACCESS_KEY:
        raise MomoConfigurationError("MoMo chưa được cấu hình MOMO_ACCESS_KEY.")
    raw = "&".join(
        f"{key}={settings.MOMO_ACCESS_KEY if key == 'accessKey' else data.get(key, '')}"
        for key in fields
    )
    return hmac.new(
        _secret_key().encode("utf-8"),
        raw.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


REQUEST_SIGNATURE_FIELDS = (
    "accessKey",
    "amount",
    "extraData",
    "ipnUrl",
    "orderId",
    "orderInfo",
    "partnerCode",
    "redirectUrl",
    "requestId",
    "requestType",
)

RESPONSE_SIGNATURE_FIELDS = (
    "accessKey",
    "amount",
    "extraData",
    "message",
    "orderId",
    "orderInfo",
    "orderType",
    "partnerCode",
    "payType",
    "requestId",
    "responseTime",
    "resultCode",
    "transId",
)


def verify_momo_signature(data):
    supplied_signature = data.get("signature", "")
    if not isinstance(supplied_signature, str) or not supplied_signature:
        return False
    try:
        expected_signature = _signature(data, RESPONSE_SIGNATURE_FIELDS)
    except MomoConfigurationError:
        return False
    return hmac.compare_digest(supplied_signature, expected_signature)


def _validate_public_url(value, setting_name):
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise MomoConfigurationError(
            f"{setting_name} phải là URL HTTPS công khai để MoMo truy cập."
        )
    return value


def create_momo_payment(payment):
    required = {
        "MOMO_PARTNER_CODE": settings.MOMO_PARTNER_CODE,
        "MOMO_ACCESS_KEY": settings.MOMO_ACCESS_KEY,
        "MOMO_SECRET_KEY": settings.MOMO_SECRET_KEY,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise MomoConfigurationError(
            "Thiếu cấu hình MoMo: " + ", ".join(missing)
        )

    redirect_url = _validate_public_url(
        settings.MOMO_REDIRECT_URL,
        "MOMO_REDIRECT_URL",
    )
    ipn_url = _validate_public_url(settings.MOMO_IPN_URL, "MOMO_IPN_URL")
    amount = int(payment.amount)
    data = {
        "partnerCode": settings.MOMO_PARTNER_CODE,
        "requestId": str(payment.request_id),
        "amount": amount,
        "orderId": str(payment.order_id),
        "orderInfo": (
            f"Thanh toan dat phong {payment.booking.reference_code}"
        ),
        "redirectUrl": redirect_url,
        "ipnUrl": ipn_url,
        "requestType": "captureWallet",
        "extraData": "",
        "lang": "vi",
    }
    data["signature"] = _signature(data, REQUEST_SIGNATURE_FIELDS)
    request = Request(
        settings.MOMO_ENDPOINT,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=15) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise MomoGatewayError(
            f"MoMo trả về lỗi HTTP {exc.code} khi tạo giao dịch."
        ) from exc
    except (
        OSError,
        HTTPException,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise MomoGatewayError(
            "Không thể kết nối hoặc đọc phản hồi từ MoMo."
        ) from exc

    if not isinstance(response_data, dict):
        raise MomoGatewayError("MoMo trả về dữ liệu không hợp lệ.")
    if not verify_momo_signature(response_data):
        raise MomoGatewayError("Chữ ký phản hồi từ MoMo không hợp lệ.")
    if (
        str(response_data.get("partnerCode")) != settings.MOMO_PARTNER_CODE
        or str(response_data.get("requestId")) != str(payment.request_id)
        or str(response_data.get("orderId")) != str(payment.order_id)
        or str(response_data.get("amount")) != str(amount)
    ):
        raise MomoGatewayError("Thông tin giao dịch MoMo không khớp.")
    try:
        result_code = int(response_data.get("resultCode"))
    except (TypeError, ValueError):
        raise MomoGatewayError("MoMo trả về mã kết quả không hợp lệ.")
    if result_code != 0:
        logger.warning(
            "MoMo rejected payment order %s with resultCode %s",
            payment.order_id,
            response_data.get("resultCode"),
        )
        raise MomoGatewayError("MoMo không thể tạo giao dịch thanh toán.")

    pay_url = response_data.get("payUrl", "")
    if not isinstance(pay_url, str):
        raise MomoGatewayError("Đường dẫn thanh toán MoMo không hợp lệ.")
    parsed_pay_url = urlparse(pay_url)
    if (
        parsed_pay_url.scheme != "https"
        or parsed_pay_url.hostname not in {
            "test-payment.momo.vn",
            "payment.momo.vn",
        }
    ):
        raise MomoGatewayError("Đường dẫn thanh toán MoMo không hợp lệ.")
    return pay_url
