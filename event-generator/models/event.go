package models

type SensorData struct {
	DoorAngle                *float64 `json:"door_angle"`
	MotionConfidence         *float64 `json:"motion_confidence"`
	ClassificationLabel      *string  `json:"classification_label"`
	ClassificationConfidence *float64 `json:"classification_confidence"`
	SignalStrength           *float64 `json:"signal_strength"`
	FirmwareVersion          *string  `json:"firmware_version"`
}

type Event struct {
	ID        string     `json:"id"`
	Type      string     `json:"type"`
	HomeID    string     `json:"home_id"`
	DeviceID  string     `json:"device_id"`
	Timestamp string     `json:"timestamp"`
	Location  string     `json:"location"`
	RawData   SensorData `json:"raw_data"`
}
