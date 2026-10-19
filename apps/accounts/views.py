"""
Vistas de acceso al sistema.

Estas vistas solo transportan datos: validan el formulario, invocan el servicio
de dominio y crean o destruyen la sesión. No contienen reglas de negocio.
"""

from __future__ import annotations

import logging
from io import BytesIO

import qrcode
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.accounts.exceptions import (
    AccountLockedError,
    AuthenticationDomainError,
    CorreoYaRegistradoError,
    InvalidCredentialsError,
    InvitacionInvalidaError,
    TwoFactorInvalidCodeError,
    TwoFactorStateError,
)
from apps.accounts.forms import (
    DefinirContrasenaForm,
    InvitacionForm,
    PasswordLoginForm,
    TotpCodeForm,
    TwoFactorPasswordForm,
)
from apps.accounts.models import Invitacion, User
from apps.accounts.services import (
    build_invitacion_service,
    build_login_service,
    get_client_ip,
)
from apps.accounts.services.two_factor import (
    TwoFactorService,
    build_two_factor_service,
    totp_provisioning_uri,
)

logger = logging.getLogger(__name__)

LOGIN_TEMPLATE = "accounts/login.html"

GENERIC_CREDENTIALS_ERROR = "Correo o contraseña incorrectos."
PREAUTH_USER_SESSION_KEY = "two_factor_pending_user_id"
PREAUTH_STARTED_SESSION_KEY = "two_factor_pending_started_at"
PREAUTH_SESSION_SECONDS = 300
TWO_FACTOR_TEMPLATE = "accounts/two_factor.html"


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

    if request.method == "POST" and request.POST.get("action") == "verify_totp":
        return _handle_totp_login(request)
    if request.method == "POST" and request.POST.get("action") == "cancel_totp":
        _clear_two_factor_login(request)
        messages.info(request, "Verificación cancelada. Ingresa nuevamente.")
        return redirect("accounts:login")

    pending_user = _pending_two_factor_user(request)
    if pending_user is not None:
        return _render_totp_login(request)

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
            if user.totp_enabled:
                request.session[PREAUTH_USER_SESSION_KEY] = user.pk
                request.session[PREAUTH_STARTED_SESSION_KEY] = timezone.now().timestamp()
                request.session.set_expiry(PREAUTH_SESSION_SECONDS)
                return _render_totp_login(request)
            auth_login(request, user)
            return redirect(_resolve_redirect(request, reverse("workshop:buscar")))

    return render(
        request,
        LOGIN_TEMPLATE,
        {
            "password_form": form,
            "next": _resolve_redirect(request, ""),
        },
    )


def _pending_two_factor_user(request: HttpRequest) -> User | None:
    user_id = request.session.get(PREAUTH_USER_SESSION_KEY)
    started_at = request.session.get(PREAUTH_STARTED_SESSION_KEY)
    if not isinstance(user_id, int) or not isinstance(started_at, (int, float)):
        _clear_two_factor_login(request)
        return None
    if timezone.now().timestamp() - started_at > PREAUTH_SESSION_SECONDS:
        _clear_two_factor_login(request)
        return None
    user = User.objects.filter(pk=user_id, is_active=True, totp_enabled=True).first()
    if user is None:
        _clear_two_factor_login(request)
    return user


def _clear_two_factor_login(request: HttpRequest) -> None:
    request.session.pop(PREAUTH_USER_SESSION_KEY, None)
    request.session.pop(PREAUTH_STARTED_SESSION_KEY, None)


def _render_totp_login(request: HttpRequest, *, form: TotpCodeForm | None = None) -> HttpResponse:
    return render(
        request,
        LOGIN_TEMPLATE,
        {
            "password_form": PasswordLoginForm(),
            "totp_required": True,
            "totp_form": form or TotpCodeForm(),
            "next": _resolve_redirect(request, ""),
        },
    )


def _handle_totp_login(request: HttpRequest) -> HttpResponse:
    user = _pending_two_factor_user(request)
    if user is None:
        messages.error(
            request,
            "La verificación expiró. Ingresa nuevamente tu correo y contraseña.",
        )
        return redirect("accounts:login")

    form = TotpCodeForm(request.POST)
    if not form.is_valid():
        return _render_totp_login(request, form=form)

    try:
        build_two_factor_service().verify_login_code(
            user=user,
            code=form.cleaned_data["code"],
            client_ip=get_client_ip(request),
        )
    except AccountLockedError as exc:
        messages.error(
            request,
            f"Demasiados intentos. Intenta nuevamente en {_format_wait(exc.retry_after_seconds)}.",
        )
        return _render_totp_login(request, form=form)
    except TwoFactorInvalidCodeError:
        messages.error(request, "El código no es válido o ya fue utilizado.")
        return _render_totp_login(request, form=form)
    except TwoFactorStateError:
        _clear_two_factor_login(request)
        messages.error(request, "La configuración de dos pasos cambió. Ingresa nuevamente.")
        return redirect("accounts:login")

    _clear_two_factor_login(request)
    auth_login(request, user)
    request.session.set_expiry(None)
    return redirect(_resolve_redirect(request, reverse("workshop:buscar")))


@never_cache
def two_factor_settings(request: HttpRequest) -> HttpResponse:
    """Configura opcionalmente una aplicación TOTP para la cuenta actual."""
    service = build_two_factor_service()
    if request.method == "POST":
        action = request.POST.get("action")
        form = TwoFactorPasswordForm(request.POST)

        if action in {"enable", "disable"} and form.is_valid():
            if not form.cleaned_data["code"]:
                form.add_error("code", "Ingresa el código de tu aplicación autenticadora.")
            else:
                try:
                    if action == "enable":
                        service.enable(
                            user=request.user,
                            password=form.cleaned_data["password"],
                            code=form.cleaned_data["code"],
                            client_ip=get_client_ip(request),
                        )
                        messages.success(request, "Autenticación en dos pasos activada.")
                    else:
                        service.disable(
                            user=request.user,
                            password=form.cleaned_data["password"],
                            code=form.cleaned_data["code"],
                            client_ip=get_client_ip(request),
                        )
                        messages.success(request, "Autenticación en dos pasos desactivada.")
                    return redirect("accounts:two_factor")
                except AccountLockedError as exc:
                    messages.error(
                        request,
                        f"Demasiados intentos. Espera {_format_wait(exc.retry_after_seconds)}.",
                    )
                except InvalidCredentialsError:
                    form.add_error("password", "La contraseña actual no es correcta.")
                except TwoFactorInvalidCodeError:
                    form.add_error("code", "El código no es válido o ya fue utilizado.")
                except TwoFactorStateError as exc:
                    messages.error(request, str(exc))

        elif action == "begin" and form.is_valid():
            try:
                service.begin_setup(
                    user=request.user,
                    password=form.cleaned_data["password"],
                    client_ip=get_client_ip(request),
                )
                messages.info(request, "Escanea el QR y confirma con un código vigente.")
                return redirect("accounts:two_factor")
            except AccountLockedError as exc:
                messages.error(
                    request,
                    f"Demasiados intentos. Espera {_format_wait(exc.retry_after_seconds)}.",
                )
            except InvalidCredentialsError:
                form.add_error("password", "La contraseña actual no es correcta.")
            except TwoFactorStateError as exc:
                messages.error(request, str(exc))
        elif action not in {"begin", "enable", "disable"}:
            messages.error(request, "Acción de seguridad no válida.")

        return _render_two_factor_settings(request, service, form=form)

    return _render_two_factor_settings(request, service)


def _render_two_factor_settings(
    request: HttpRequest,
    service: TwoFactorService,
    *,
    form: TwoFactorPasswordForm | None = None,
) -> HttpResponse:
    pending_secret = service.pending_secret(user=request.user)
    return render(
        request,
        TWO_FACTOR_TEMPLATE,
        {
            "form": form or TwoFactorPasswordForm(),
            "pending_secret": pending_secret,
            "qr_url": reverse("accounts:two_factor_qr") if pending_secret else "",
        },
    )


@never_cache
def two_factor_qr(request: HttpRequest) -> HttpResponse:
    """Entrega un QR TOTP privado para el usuario autenticado actual."""
    service = build_two_factor_service()
    secret = service.pending_secret(user=request.user)
    if secret is None:
        return HttpResponse(status=404)

    uri = totp_provisioning_uri(email=request.user.email, secret=secret)
    image = qrcode.make(uri)
    output = BytesIO()
    image.save(output, format="PNG")
    response = HttpResponse(output.getvalue(), content_type="image/png")
    response["Cache-Control"] = "private, no-store"
    response["Pragma"] = "no-cache"
    return response


# ---------------------------------------------------------------------------
# Cierre de sesión
# ---------------------------------------------------------------------------


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    """Cierra la sesión. Solo por POST para evitar cierres por prefetch del navegador."""
    auth_logout(request)
    messages.info(request, "Cerraste sesión correctamente.")
    return redirect("accounts:login")


# ---------------------------------------------------------------------------
# Invitaciones
#
# El sistema es de uso interno y no tiene registro público: la única forma de
# obtener una cuenta es que alguien que ya está dentro la invite.
# ---------------------------------------------------------------------------

INVITACIONES_TEMPLATE = "accounts/invitaciones.html"
INVITACION_INVALIDA_TEMPLATE = "accounts/invitacion_invalida.html"
GENERIC_INVITACION_ERROR = "No pudimos emitir la invitación. Intenta nuevamente."


def invitaciones(request: HttpRequest) -> HttpResponse:
    """Emite invitaciones y muestra las que siguen pendientes."""
    if not request.user.is_staff:
        # Denegación por defecto: invitar concede acceso al sistema, así que no
        # basta con estar autenticado. El enlace del token nunca se persiste en
        # claro, por eso se muestra una sola vez aquí.
        raise PermissionDenied("Solo el personal con acceso al panel puede invitar.")

    form = InvitacionForm(request.POST or None)
    emitida = None

    if request.method == "POST" and form.is_valid():
        try:
            emitida = build_invitacion_service().invitar(
                email=form.cleaned_data["email"],
                invitado_por=request.user,
                base_url=request.build_absolute_uri("/"),
            )
        except CorreoYaRegistradoError as exc:
            form.add_error("email", str(exc))
        except AuthenticationDomainError:
            logger.exception("Fallo al emitir una invitación.")
            messages.error(request, GENERIC_INVITACION_ERROR)
        else:
            form = InvitacionForm()

    contexto = {
        "form": form,
        "emitida": emitida,
        "pendientes": Invitacion.objects.vigentes().select_related("invited_by"),
    }
    return render(request, INVITACIONES_TEMPLATE, contexto)


@login_not_required
def aceptar_invitacion(request: HttpRequest, token: str) -> HttpResponse:
    """Pantalla donde la persona invitada define su contraseña."""
    if request.user.is_authenticated:
        return redirect("workshop:buscar")

    servicio = build_invitacion_service()

    try:
        invitacion = servicio.obtener_utilizable(token)
    except InvitacionInvalidaError:
        return render(request, INVITACION_INVALIDA_TEMPLATE, status=410)

    # El formulario necesita un usuario para el validador de similitud; todavía
    # no está guardado, solo sirve de contexto para comparar.
    form = DefinirContrasenaForm(User(email=invitacion.email), request.POST or None)

    if request.method == "POST" and form.is_valid():
        try:
            usuario = servicio.aceptar(token=token, password=form.cleaned_data["new_password1"])
        except InvitacionInvalidaError:
            return render(request, INVITACION_INVALIDA_TEMPLATE, status=410)
        except CorreoYaRegistradoError:
            messages.error(
                request,
                "Ese correo ya tiene una cuenta. Ingresa con tu contraseña.",
            )
            return redirect("accounts:login")
        else:
            auth_login(request, usuario)
            messages.success(request, "Tu cuenta está lista. Bienvenida/o al sistema.")
            return redirect("workshop:buscar")

    return render(
        request,
        "accounts/invitacion_aceptar.html",
        {"form": form, "invitacion": invitacion},
    )
