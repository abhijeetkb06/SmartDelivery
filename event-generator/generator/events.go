package generator

import (
	"fmt"
	"math/rand"
	"time"

	"smart-delivery/event-generator/models"
)

func BuildEvents(tmpl ScenarioTemplate, home models.Home, baseTime time.Time, seqStart int) []models.Event {
	events := make([]models.Event, 0, len(tmpl.Events))
	cursor := baseTime

	for i, et := range tmpl.Events {
		// Apply random delay within range
		delaySec := et.DelayMin
		if et.DelayMax > et.DelayMin {
			delaySec += rand.Float64() * (et.DelayMax - et.DelayMin)
		}
		cursor = cursor.Add(time.Duration(delaySec * float64(time.Second)))

		// Pick a device from the home that matches the location
		deviceID := pickDevice(home, et.Location)

		// Build sensor data
		raw := models.SensorData{}
		switch et.EventType {
		case "door_open":
			angle := 90.0 + rand.Float64()*5
			raw.DoorAngle = &angle
		case "door_close":
			angle := 0.0
			raw.DoorAngle = &angle
		case "door_stuck":
			angle := 85.0 + rand.Float64()*10
			raw.DoorAngle = &angle
		}

		if et.ClassificationLabel != "" {
			label := et.ClassificationLabel
			conf := et.ClassificationConfidence + (rand.Float64()*0.06 - 0.03)
			if conf > 1 {
				conf = 1
			}
			if conf < 0 {
				conf = 0
			}
			raw.ClassificationLabel = &label
			raw.ClassificationConfidence = &conf
		}

		if et.EventType == "camera_motion" || et.EventType == "person_detected" || et.EventType == "unknown_person" {
			mc := 0.75 + rand.Float64()*0.25
			raw.MotionConfidence = &mc
		}

		sig := -30.0 - rand.Float64()*40
		fw := home.Devices[0].Firmware
		raw.SignalStrength = &sig
		raw.FirmwareVersion = &fw

		events = append(events, models.Event{
			ID:        fmt.Sprintf("evt-%06d", seqStart+i),
			Type:      et.EventType,
			HomeID:    home.ID,
			DeviceID:  deviceID,
			Timestamp: cursor.Format(time.RFC3339),
			Location:  et.Location,
			RawData:   raw,
		})
	}
	return events
}

func pickDevice(home models.Home, location string) string {
	for _, d := range home.Devices {
		if d.Location == location {
			return d.DeviceID
		}
	}
	// Fallback: map driveway to front_door camera, behind_vehicle to garage
	switch location {
	case "driveway", "behind_vehicle":
		for _, d := range home.Devices {
			if d.Location == "garage" && d.Type == "garage_camera" {
				return d.DeviceID
			}
		}
	}
	if len(home.Devices) > 0 {
		return home.Devices[0].DeviceID
	}
	return "unknown"
}
