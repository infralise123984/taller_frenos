from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_invitacion"),
    ]

    operations = [
        migrations.DeleteModel(
            name="OtpChallenge",
        ),
        migrations.RemoveField(
            model_name="user",
            name="last_otp_login",
        ),
    ]
