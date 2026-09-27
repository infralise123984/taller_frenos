"""
Vistas de acceso al sistema.

Estas vistas solo transportan datos: validan el formulario, invocan el servicio
de dominio y crean o destruyen la sesión. No contienen reglas de negocio.
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_not_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.accounts.exceptions import (
    AccountInactiveError,
    AccountLockedError,
    AuthenticationDomainError,
    InvalidCredentialsError,
    OtpThrottledError,
)
from apps.accounts.forms import OtpRequestForm, OtpVerifyForm, PasswordLoginForm
from apps.accounts.services import build_login_service, get_client_ip

logger = logging.getLogger(__name__)

LOGIN_TEMPLATE = "accounts/login.html"

GENERIC_CREDENTIALS_ERROR = "Correo o contraseña incorrectos."
GENERIC_CODE_ERROR = "El código no es válido o ya expiró. Puedes solicitar uno nuevo."
GENERIC_DELIVERY_ERROR = "No pudimos enviar el código en este momento. Intenta más tarde."
GENERIC_UNAVAILABLE_ERROR = "El servicio de códigos no está disponible. Usa tu contraseña."


def _format_wait(seconds: int) -> str:
    """Traduce segundos a un texto humano breve."""
    if seconds >= 60:
        return f"{seconds // 60} minuto(s)"
    return f"{max(1, seconds)} segundo(s)"


def _resolve_redirect(request: HttpRequest, fallback: str) -> str:
    """Valida el parámetro 'next' para evitar redirecciones abiertas."""
    candidate = request.POST.get("next") or request.GET.get("next")
    if candidate and url_has_allowed_host_and_scheme(
        url=candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback


# ---------------------------------------------------------------------------
# Acceso con contraseña
# ---------------------------------------------------------------------------


@login_not_required
def login_password(request: HttpRequest) -> HttpResponse:
    """Inicio de sesión con correo y contraseña."""
    if request.user.is_authenticated:
        return redirect("workshop:buscar")

    form = PasswordLoginForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            user = build_login_service().authenticate_with_password(
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
                client_ip=get_client_ip(request),
            )
        except AccountLockedError as exc:
            messages.error(
                request,
                f"Demasiados intentos fallidos. Intenta nuevamente en "
                f"{_format_wait(exc.retry_after_seconds)}.",
            )
        except InvalidCredentialsError:
            messages.error(request, GENERIC_CREDENTIALS_ERROR)
        except AuthenticationDomainError:
            # Cualquier otro fallo de dominio se trata de forma genérica; el
            # detalle técnico solo queda en los logs del servidor.
            logger.exception("Fallo inesperado en el acceso con contraseña.")
            messages.error(request, GENERIC_CREDENTIALS_ERROR)
        else:
            auth_login(request, user)
            return redirect(_resolve_redirect(request, reverse("workshop:buscar")))

    return render(
        request,
        LOGIN_TEMPLATE,
        {
            "password_form": form,
            "active_tab": "password",
            "next": _resolve_redirect(request, ""),
        },
    )


# ---------------------------------------------------------------------------
# Acceso con código temporal
# ---------------------------------------------------------------------------

ACTION_REQUEST = "request"
ACTION_VERIFY = "verify"


@login_not_required
def login_otp(request: HttpRequest) -> HttpResponse:
    """
    Acceso en dos pasos: se solicita el código y luego se valida.

    El paso se determina con el campo explícito ``action`` en lugar de inferirlo
    del estado del formulario.
    """
    if request.user.is_authenticated:
        return redirect("workshop:buscar")

    action = request.POST.get("action", "")

    if request.method == "POST" and action == ACTION_REQUEST:
        return _handle_otp_request(request)
    if request.method == "POST" and action == ACTION_VERIFY:
        return _handle_otp_verification(request)

    return render(
        request,
        LOGIN_TEMPLATE,
        {
            "otp_request_form": OtpRequestForm(),
            "active_tab": "otp",
            "next": _resolve_redirect(request, ""),
        },
    )


def _handle_otp_request(request: HttpRequest) -> HttpResponse:
    form = OtpRequestForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            LOGIN_TEMPLATE,
            {"otp_request_form": form, "active_tab": "otp"},
        )

    email = form.cleaned_data["email"]
    try:
        build_login_service().request_otp(email=email, client_ip=get_client_ip(request))
    except OtpThrottledError as exc:
        messages.error(
            request,
            "Solicitaste códigos muy seguido. Espera "
            f"{_format_wait(exc.retry_after_seconds)} antes de pedir otro.",
        )
        return render(
            request,
            LOGIN_TEMPLATE,
            {"otp_request_form": form, "active_tab": "otp"},
        )
    except AuthenticationDomainError:
        logger.exception("Fallo al solicitar el código de acceso.")
        messages.error(request, GENERIC_DELIVERY_ERROR)
        return render(
            request,
            LOGIN_TEMPLATE,
            {"otp_request_form": form, "active_tab": "otp"},
        )

    messages.success(request, f"Si {email} está registrado, recibirá un código en breve.")
    return render(
        request,
        LOGIN_TEMPLATE,
        {
            "otp_verify_form": OtpVerifyForm(initial={"email": email}),
            "otp_email": email,
            "next": _resolve_redirect(request, ""),
            "active_tab": "otp",
            "step": ACTION_VERIFY,
        },
    )


def _handle_otp_verification(request: HttpRequest) -> HttpResponse:
    form = OtpVerifyForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            LOGIN_TEMPLATE,
            {"otp_verify_form": form, "active_tab": "otp", "step": ACTION_VERIFY},
        )

    email = form.cleaned_data["email"]
    try:
        user = build_login_service().authenticate_with_otp(
            email=email,
            code=form.cleaned_data["code"],
            client_ip=get_client_ip(request),
        )
    except AccountInactiveError:
        messages.error(request, "Tu cuenta está deshabilitada. Contacta al administrador.")
        return render(
            request,
            LOGIN_TEMPLATE,
            {"otp_request_form": OtpRequestForm(initial={"email": email}), "active_tab": "otp"},
        )
    except AuthenticationDomainError:
        logger.info("Código de acceso rechazado para %s.", email)
        messages.error(request, GENERIC_CODE_ERROR)
        return render(
            request,
            LOGIN_TEMPLATE,
            {
                "otp_verify_form": OtpVerifyForm(initial={"email": email}),
                "otp_email": email,
                "active_tab": "otp",
                "step": ACTION_VERIFY,
            },
        )

    auth_login(request, user)
    return redirect(_resolve_redirect(request, reverse("workshop:buscar")))


# ---------------------------------------------------------------------------
# Cierre de sesión
# ---------------------------------------------------------------------------


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    """Cierra la sesión. Solo por POST para evitar cierres por prefetch del navegador."""
    auth_logout(request)
    messages.info(request, "Cerraste sesión correctamente.")
    return redirect("accounts:login")
