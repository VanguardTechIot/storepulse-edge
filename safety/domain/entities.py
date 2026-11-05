from datetime import datetime, time, timedelta, timezone

SENSOR_TYPES = ("MOTION", "SMOKE", "HUMIDITY", "TEMPERATURE", "ELECTRICITY", "WATER")

OPERATORS = {
    "GREATER_THAN": lambda value, limit: value > limit,
    "GREATER_THAN_OR_EQUAL": lambda value, limit: value >= limit,
    "LESS_THAN": lambda value, limit: value < limit,
    "LESS_THAN_OR_EQUAL": lambda value, limit: value <= limit,
    "EQUAL": lambda value, limit: value == limit,
}


class BusinessHours:
    ZONE = timezone(timedelta(hours=-5))
    OPENING = time(10, 0)
    CLOSING = time(22, 0)

    @classmethod
    def includes(cls, instant: datetime) -> bool:
        local_time = instant.astimezone(cls.ZONE).time()
        return cls.OPENING <= local_time < cls.CLOSING


class SafetyRule:
    def __init__(self, name: str, sensor_type: str, threshold_value: float, threshold_operator: str,
                 enabled: bool = True):
        if not name or not name.strip():
            raise ValueError("Safety rule name is required")
        if sensor_type not in SENSOR_TYPES:
            raise ValueError(f"Unknown sensor type: {sensor_type}")
        if threshold_operator not in OPERATORS:
            raise ValueError(f"Unknown threshold operator: {threshold_operator}")
        self.name = name.strip()
        self.sensor_type = sensor_type
        self.threshold_value = float(threshold_value)
        self.threshold_operator = threshold_operator
        self.enabled = enabled

    def is_triggered_by(self, value: float, recorded_at: datetime) -> bool:
        if not self.enabled or not OPERATORS[self.threshold_operator](value, self.threshold_value):
            return False
        return self.sensor_type != "MOTION" or not BusinessHours.includes(recorded_at)


class MeasurementAssessment:
    def __init__(self, sensor_type: str, device_status: str, response: str):
        self.sensor_type = sensor_type
        self.device_status = device_status
        self.response = response

    @classmethod
    def normal(cls, sensor_type: str):
        return cls(sensor_type, "NORMAL", "NONE")

    @classmethod
    def alert(cls, sensor_type: str):
        return cls(sensor_type, "ALERT", "SEND_ALERT")
