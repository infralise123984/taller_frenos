"""Formularios de la app de cuentas."""

from __future__ import annotations

from django import forms

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
                "class": TEXT_INPUT_CLASSES,
                "placeholder": "••••••••",
                "autocomplete": "current-password",
            }
        ),
    )


class OtpRequestForm(forms.Form):
    """Paso 1 del acceso con código temporal."""

    email = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(
            attrs={
                "class": TEXT_INPUT_CLASSES,
                "placeholder": "taller@ejemplo.cl",
                "autocomplete": "email",
                "inputmode": "email",
                "autofocus": True,
            }
        ),
    )


class OtpVerifyForm(forms.Form):
    """Paso 2: el código que llegó al correo."""

    email = forms.EmailField(widget=forms.HiddenInput)
    code = forms.CharField(
        label="Código de 6 dígitos",
        max_length=12,
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
        code = self.cleaned_data["code"].strip().replace(" ", "")
        if not code.isdigit():
            raise forms.ValidationError("El código debe contener solo números.")
        return code
