"""
Convierte la intervención de la visita en una línea de ficha con precio.

Los renombres se hacen con ``RenameField`` (y no borrando y creando) para no
perder lo que ya esté cargado en los entornos de desarrollo. No hay conversión
de datos: el catálogo de tipos cambia de nombre y las filas existentes, si las
hubiera, conservan su valor tal cual.
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models

TOPE_PRECIO = 10_000_000


class Migration(migrations.Migration):
    dependencies = [
        ("workshop", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="itemtrabajo",
            old_name="descripcion",
            new_name="detalle",
        ),
        migrations.RenameField(
            model_name="itemtrabajo",
            old_name="repuesto",
            new_name="codigo_repuesto",
        ),
        migrations.AddField(
            model_name="itemtrabajo",
            name="marca_repuesto",
            field=models.CharField(blank=True, max_length=60, verbose_name="marca del repuesto"),
        ),
        migrations.AddField(
            model_name="itemtrabajo",
            name="precio",
            field=models.IntegerField(
                default=0,
                help_text="Pesos chilenos. Negativo solo en la línea de descuento.",
                validators=[
                    MinValueValidator(-TOPE_PRECIO),
                    MaxValueValidator(TOPE_PRECIO),
                ],
                verbose_name="precio",
            ),
        ),
        migrations.AlterField(
            model_name="itemtrabajo",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("pastillas", "Pastillas"),
                    ("rect_disco", "Rect. Disco"),
                    ("patines", "Patines"),
                    ("rect_tambores", "Rect. Tambores"),
                    ("gomas_cilindros", "Gomas Cilindros"),
                    ("liquido", "Líquido"),
                    ("seguro_pastillas", "Seguro Pastillas"),
                    ("rep_bomba", "Rep. Bomba"),
                    ("kit_bomba", "Kit Bomba"),
                    ("inst_piola", "Inst. Piola F/Mano"),
                    ("flexible", "Flexible"),
                    ("resorte_patin", "Resorte Patín"),
                    ("rep_caliper", "Rep. Caliper"),
                    ("regulacion_tras", "Regulación Tras."),
                    ("obra_mano", "Obra de Mano"),
                    ("descuento", "Descuento"),
                    ("otro", "Otro (escribir en el detalle)"),
                ],
                max_length=32,
                verbose_name="trabajo",
            ),
        ),
        migrations.AlterField(
            model_name="itemtrabajo",
            name="detalle",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Texto libre: posición del trabajo (delantero, trasero), observación, etc."
                ),
                max_length=250,
                verbose_name="detalle",
            ),
        ),
        migrations.AlterField(
            model_name="itemtrabajo",
            name="codigo_repuesto",
            field=models.CharField(
                blank=True, max_length=60, verbose_name="código del repuesto"
            ),
        ),
        migrations.AlterModelOptions(
            name="itemtrabajo",
            options={
                "ordering": ["id"],
                "verbose_name": "línea de la ficha",
                "verbose_name_plural": "líneas de la ficha",
            },
        ),
        migrations.CreateModel(
            name="DatosTaller",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("direccion", models.CharField(blank=True, max_length=200, verbose_name="dirección")),
                ("ciudad", models.CharField(blank=True, max_length=80, verbose_name="ciudad")),
                (
                    "telefono",
                    models.CharField(
                        blank=True,
                        help_text="Tal como debe salir impreso, por ejemplo 225 384 512.",
                        max_length=32,
                        verbose_name="teléfono",
                    ),
                ),                (
                    "actualizado_el",
                    models.DateTimeField(auto_now=True, verbose_name="actualizado el"),
                ),
            ],
            options={
                "verbose_name": "datos del taller",
                "verbose_name_plural": "datos del taller",
            },
        ),
    ]
