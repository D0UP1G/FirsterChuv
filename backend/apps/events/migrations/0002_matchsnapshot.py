from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("events", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="MatchSnapshot",
            fields=[
                ("match_id", models.UUIDField(primary_key=True, serialize=False)),
                ("run_id", models.UUIDField()),
                ("last_event_id", models.PositiveBigIntegerField(default=0)),
                ("payload", models.JSONField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"constraints": [models.CheckConstraint(condition=models.Q(("last_event_id__gte", 0)), name="events_snapshot_nonnegative_cursor")]},
        ),
    ]
