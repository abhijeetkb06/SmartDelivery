package generator

import (
	"fmt"
	"math/rand"
	"time"

	"smart-delivery/event-generator/models"
)

var carriers = []string{"UPS", "FedEx", "USPS", "Amazon", "DHL"}

func BuildDelivery(idx int, home models.Home, tmpl ScenarioTemplate, events []models.Event) (models.Delivery, *models.Alert) {
	now := time.Now().UTC()

	eventIDs := make([]string, len(events))
	timeline := make([]models.TimelineEntry, len(events))
	for i, e := range events {
		eventIDs[i] = e.ID
		timeline[i] = models.TimelineEntry{
			EventID:   e.ID,
			EventType: e.Type,
			Location:  e.Location,
			Summary:   summaryFor(e.Type, e.Location),
			Timestamp: e.Timestamp,
		}
	}

	riskScore := tmpl.RiskScoreMin + rand.Float64()*(tmpl.RiskScoreMax-tmpl.RiskScoreMin)

	actualTime := ""
	if tmpl.DeliveryStatus == "completed_success" || tmpl.DeliveryStatus == "completed_risk" {
		if len(events) > 0 {
			actualTime = events[len(events)-1].Timestamp
		}
	}

	windowStart := now.Add(-4 * time.Hour)
	windowEnd := now.Add(-1 * time.Hour)

	del := models.Delivery{
		ID:                  fmt.Sprintf("del-%05d", idx+1),
		HomeID:              home.ID,
		Address:             fmt.Sprintf("%s, %s, %s %s", home.Address, home.City, home.State, home.ZipCode),
		OwnerName:           home.OwnerName,
		Status:              tmpl.DeliveryStatus,
		ScenarioType:        tmpl.ScenarioType,
		Carrier:             carriers[rand.Intn(len(carriers))],
		ExpectedWindowStart: windowStart.Format(time.RFC3339),
		ExpectedWindowEnd:   windowEnd.Format(time.RFC3339),
		ActualDeliveryTime:  actualTime,
		DeliveryLocation:    tmpl.DeliveryLocation,
		EventIDs:            eventIDs,
		EventTimeline:       timeline,
		RiskScore:           riskScore,
		RiskFactors:         tmpl.RiskFactors,
		CreatedAt:           now.Format(time.RFC3339),
		UpdatedAt:           now.Format(time.RFC3339),
		ProcessingStatus:    "pending",
	}
	if del.RiskFactors == nil {
		del.RiskFactors = []string{}
	}

	var alert *models.Alert
	if tmpl.AlertType != "" {
		severity := severityFor(tmpl.AlertType)
		alert = &models.Alert{
			ID:              fmt.Sprintf("alert-%05d", idx+1),
			DeliveryID:      del.ID,
			HomeID:          home.ID,
			Address:         del.Address,
			AlertType:       tmpl.AlertType,
			Severity:        severity,
			Message:         alertMessage(tmpl.AlertType, home.Address),
			TriggeredAt:     now.Format(time.RFC3339),
			Acknowledged:    false,
			RelatedEventIDs: eventIDs,
		}
	}

	return del, alert
}

func summaryFor(eventType, location string) string {
	switch eventType {
	case "delivery_window_start":
		return "Delivery window opened"
	case "delivery_window_end":
		return "Delivery window expired"
	case "person_detected":
		return fmt.Sprintf("Person detected at %s", location)
	case "door_open":
		return "Garage door opened"
	case "door_close":
		return "Garage door closed"
	case "door_stuck":
		return "Garage door stuck open - alert triggered"
	case "camera_motion":
		return fmt.Sprintf("Motion detected at %s", location)
	case "package_detected":
		return fmt.Sprintf("Package detected at %s", location)
	case "package_not_detected":
		return "No package detected after door opened"
	case "delivery_confirmed":
		return "Delivery confirmed successfully"
	case "delivery_timeout":
		return "Delivery timed out - no activity detected"
	case "unknown_person":
		return "Unknown person detected near package"
	default:
		return eventType
	}
}

func severityFor(alertType string) string {
	switch alertType {
	case "theft_risk":
		return "critical"
	case "door_stuck", "package_at_risk":
		return "high"
	case "misdelivery", "no_package":
		return "medium"
	case "delivery_timeout":
		return "low"
	default:
		return "medium"
	}
}

func alertMessage(alertType, address string) string {
	switch alertType {
	case "misdelivery":
		return fmt.Sprintf("Package delivered to front door instead of garage at %s", address)
	case "package_at_risk":
		return fmt.Sprintf("Package placed behind vehicle in garage at %s - crush risk", address)
	case "door_stuck":
		return fmt.Sprintf("Garage door stuck open at %s - security risk", address)
	case "no_package":
		return fmt.Sprintf("Garage door opened but no package detected at %s", address)
	case "delivery_timeout":
		return fmt.Sprintf("Expected delivery not received at %s - window expired", address)
	case "theft_risk":
		return fmt.Sprintf("Suspicious activity detected near package at %s - possible theft", address)
	default:
		return fmt.Sprintf("Alert at %s: %s", address, alertType)
	}
}
