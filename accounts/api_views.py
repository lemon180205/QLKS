from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny

from .forms import CustomerRegistrationForm

class CurrentUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        return Response({
            "id": user.pk,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone": user.phone,
        })
class RegisterAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        form = CustomerRegistrationForm(data=request.data)

        if not form.is_valid():
            raise ValidationError({
                field: list(errors)
                for field, errors in form.errors.items()
            })

        user = form.save()

        return Response(
            {
                "id": user.pk,
                "username": user.username,
                "email": user.email,
            },
            status=status.HTTP_201_CREATED,
        )