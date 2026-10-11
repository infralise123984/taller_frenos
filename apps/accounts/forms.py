"""Formularios de la app de cuentas."""

from __future__ import annotations

from django import forms
from django.contrib.auth.forms import SetPasswordForm

# Los formularios usan widgets con clases de Tailwind y atributos de teclado
# móvil, porque el sistema se usa principalmente desde tablet o teléfono.

TEXT_INPUT_CLASSES = (
    "w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-lg "
    "text-slate-900 shadow-sm placeholder:text-slate-400 "
    "focus:border-sky-600 focus:outline-none focus:ring-2 focus:ring-sky-200"
)


class PasswordLoginForm(forms.Form):
    """Acceso con correo y contraseña."""

    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(
            attrs={
                "class": TEXT_INPUT_CLASSES,
                "placeholder": "taller@ejemplo.cl",
                "autocomplete": "username",
                "autofocus": True,
                "inputmode": "email",
            }
        ),
    )
    password = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": f"{TEXT_INPUT_CLASSES} pr-12",
                "placeholder": "••••••••",
                "autocomplete": "current-password",
            }
        ),
    )


class TotpCodeForm(forms.Form):
    """Código temporal emitido por una aplicación autenticadora."""

    code = forms.CharField(
        label="Código de 6 dígitos",
        max_length=6,
        min_length=6,
        widget=forms.TextInput(
            attrs={
                "class": (
                    f"{TEXT_INPUT_CLASSES} text-center text-3xl tracking-[0.5em] font-semibold"
                ),
                "placeholder": "000000",
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
                "autofocus": True,
            }
        ),
    )

    def clean_code(self) -> str:
        code = self.cleaned_data["code"].strip()
        if not code.isdigit():
            raise forms.ValidationError("El código debe contener solo números.")
        return code


class TwoFactorPasswordForm(forms.Form):
    """Confirma contraseña y, opcionalmente, un código TOTP."""

    password = forms.CharField(
        label="Contraseña actual",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": TEXT_INPUT_CLASSES,
                "autocomplete": "current-password",
            }
        ),
    )
    code = forms.CharField(
        label="Código de 6 dígitos",
        required=False,
        max_length=6,
        min_length=6,
        widget=forms.TextInput(
            attrs={
                "class": f"{TEXT_INPUT_CLASSES} text-center tracking-[0.35em] font-semibold",
                "placeholder": "000000",
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
            }
        ),
    )

    def clean_code(self) -> str:
        code = self.cleaned_data["code"].strip()
        if code and not code.isdigit():
            raise forms.ValidationError("El código debe contener solo números.")
        return code


# ---------------------------------------------------------------------------
# Invitaciones
# ---------------------------------------------------------------------------


class InvitacionForm(forms.Form):
    """Emite una invitación para que otra persona cree su cuenta."""

    email = forms.EmailField(
        label="Correo de la persona a invitar",
        widget=forms.EmailInput(
            attrs={
                "class": TEXT_INPUT_CLASSES,
                "placeholder": "mecanico@ejemplo.cl",
                "autocomplete": "off",
                "inputmode": "email",
                "autofocus": True,
            }
        ),
    )

    def clean_email(self) -> str:
        return self.cleaned_data["email"].strip().lower()


class DefinirContrasenaForm(SetPasswordForm):
    """
    Formulario para que la persona invitada elija su contraseña.

    Se apoya en ``SetPasswordForm`` de Django a propósito: es el que aplica los
    validadores de robustez configurados en ``AUTH_PASSWORD_VALIDATORS``. Aquí
    solo se traducen las etiquetas y se aplica el estilo del sistema, porque sus
    etiquetas por defecto vienen en inglés.
    """

    # Los mensajes de Django se traducen según el locale activo, pero aquí se
    # fija el de la falta de coincidencia para que no dependa de ello.
    error_messages = {
        **SetPasswordForm.error_messages,
        "password_mismatch": "Las dos contraseñas no coinciden.",
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.fields["new_password1"].label = "Contraseña"
        self.fields["new_password2"].label = "Repite la contraseña"

        for campo in self.fields.values():
            campo.widget.attrs["class"] = TEXT_INPUT_CLASSES
            campo.widget.attrs["autocomplete"] = "new-password"

        self.fields["new_password1"].widget.attrs["autofocus"] = True
        self.fields[
            "new_password1"
        ].help_text = "Mínimo 10 caracteres. Evita palabras comunes o parecidas a tu correo."

        # Django trae aquí un texto en español formal ("introduzca la misma
        # contraseña anterior") que desentona con el resto de la interfaz.
        self.fields["new_password2"].help_text = ""
