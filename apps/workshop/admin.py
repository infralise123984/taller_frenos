"""Registro del panel de administración para la gestión del taller."""

from django.contrib import admin

from apps.workshop.models import Cliente, ItemTrabajo, OrdenTrabajo, Vehiculo


class VehiculoInline(admin.TabularInline):
    model = Vehiculo
    extra = 0
    fields = ("patente", "marca", "modelo", "anio")
    show_change_link = True


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre", "telefono", "email", "cantidad_vehiculos")
    search_fields = ("nombre", "telefono", "email")
    inlines = [VehiculoInline]


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ("patente", "marca", "modelo", "anio", "cliente")
    list_select_related = ("cliente",)
    search_fields = ("patente", "marca", "modelo", "cliente__nombre")
    autocomplete_fields = ("cliente",)


class ItemTrabajoInline(admin.TabularInline):
    model = ItemTrabajo
    extra = 1


@admin.register(OrdenTrabajo)
class OrdenTrabajoAdmin(admin.ModelAdmin):
    list_display = ("vehiculo", "fecha_ingreso", "kilometraje", "resumen_trabajos")
    list_select_related = ("vehiculo",)
    list_filter = ("fecha_ingreso",)
    date_hierarchy = "fecha_ingreso"
    search_fields = ("vehiculo__patente", "vehiculo__cliente__nombre")
    autocomplete_fields = ("vehiculo",)
    inlines = [ItemTrabajoInline]
    fieldsets = (
        ("Vehículo y visita", {"fields": ("vehiculo", "fecha_ingreso", "kilometraje")}),
        ("Detalle", {"fields": ("observaciones",)}),
        ("Próxima mantención", {"fields": ("proxima_mantencion_km", "proxima_mantencion_fecha")}),
    )


@admin.register(ItemTrabajo)
class ItemTrabajoAdmin(admin.ModelAdmin):
    list_display = ("tipo", "orden", "repuesto", "descripcion")
    list_select_related = ("orden",)
    list_filter = ("tipo",)
    search_fields = ("orden__vehiculo__patente", "descripcion", "repuesto")
