from peewee import BooleanField, CharField, FloatField, Model

from shared.infrastructure.database import db


class SafetyRuleModel(Model):
    name = CharField(unique=True)
    sensor_type = CharField()
    threshold_value = FloatField()
    threshold_operator = CharField()
    enabled = BooleanField(default=True)

    class Meta:
        database = db
        table_name = "safety_rules"
