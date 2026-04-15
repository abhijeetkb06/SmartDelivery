package generator

import "math/rand"

type EventTemplate struct {
	EventType                string
	Location                 string
	DelayMin                 float64
	DelayMax                 float64
	ClassificationLabel      string
	ClassificationConfidence float64
}

type ScenarioTemplate struct {
	ScenarioType     string
	DeliveryStatus   string
	DeliveryLocation string
	RiskScoreMin     float64
	RiskScoreMax     float64
	RiskFactors      []string
	AlertType        string // empty means no alert
	Description      string
	Events           []EventTemplate
}

type weightedScenario struct {
	template ScenarioTemplate
	weight   float64
}

var scenarios = []weightedScenario{
	// 1. Happy Path (60%)
	{weight: 0.60, template: ScenarioTemplate{
		ScenarioType: "happy_path", DeliveryStatus: "completed_success",
		DeliveryLocation: "garage_inside", RiskScoreMin: 0.0, RiskScoreMax: 0.05,
		Description: "Successful garage delivery - package placed inside, door closed",
		Events: []EventTemplate{
			{"delivery_window_start", "garage", 0, 0, "", 0},
			{"person_detected", "driveway", 1800, 7200, "delivery_driver", 0.94},
			{"door_open", "garage", 5, 15, "", 0},
			{"camera_motion", "garage", 1, 3, "person", 0.92},
			{"package_detected", "garage", 8, 25, "package", 0.96},
			{"door_close", "garage", 5, 15, "", 0},
			{"delivery_confirmed", "garage", 1, 3, "", 0},
		},
	}},
	// 2. Front Door Misdelivery (12%)
	{weight: 0.12, template: ScenarioTemplate{
		ScenarioType: "front_door_misdelivery", DeliveryStatus: "completed_risk",
		DeliveryLocation: "front_door", RiskScoreMin: 0.45, RiskScoreMax: 0.70,
		RiskFactors: []string{"package_wrong_location", "not_in_garage", "exposure_to_weather"},
		AlertType:   "misdelivery",
		Description: "Package delivered to front door instead of garage",
		Events: []EventTemplate{
			{"delivery_window_start", "garage", 0, 0, "", 0},
			{"person_detected", "driveway", 1800, 7200, "delivery_driver", 0.91},
			{"camera_motion", "front_door", 15, 40, "person", 0.89},
			{"package_detected", "front_door", 5, 15, "package", 0.93},
		},
	}},
	// 3. Package Behind Car (8%)
	{weight: 0.08, template: ScenarioTemplate{
		ScenarioType: "package_behind_car", DeliveryStatus: "completed_risk",
		DeliveryLocation: "behind_vehicle", RiskScoreMin: 0.60, RiskScoreMax: 0.85,
		RiskFactors: []string{"package_behind_vehicle", "crush_risk", "driver_may_not_see"},
		AlertType:   "package_at_risk",
		Description: "Package placed behind car in garage - risk of being run over",
		Events: []EventTemplate{
			{"delivery_window_start", "garage", 0, 0, "", 0},
			{"person_detected", "driveway", 1800, 7200, "delivery_driver", 0.93},
			{"door_open", "garage", 5, 15, "", 0},
			{"camera_motion", "garage", 1, 3, "person", 0.90},
			{"package_detected", "behind_vehicle", 8, 20, "package_near_vehicle", 0.88},
			{"door_close", "garage", 10, 25, "", 0},
		},
	}},
	// 4. Door Stuck Open (6%)
	{weight: 0.06, template: ScenarioTemplate{
		ScenarioType: "door_stuck_open", DeliveryStatus: "failed",
		DeliveryLocation: "garage_inside", RiskScoreMin: 0.75, RiskScoreMax: 0.95,
		RiskFactors: []string{"door_stuck_open", "security_risk", "weather_exposure", "garage_accessible"},
		AlertType:   "door_stuck",
		Description: "Garage door stuck open after delivery - security risk",
		Events: []EventTemplate{
			{"delivery_window_start", "garage", 0, 0, "", 0},
			{"person_detected", "driveway", 1800, 7200, "delivery_driver", 0.92},
			{"door_open", "garage", 5, 15, "", 0},
			{"camera_motion", "garage", 1, 3, "person", 0.91},
			{"package_detected", "garage", 8, 20, "package", 0.95},
			{"door_stuck", "garage", 600, 900, "", 0},
		},
	}},
	// 5. No Package Placed (6%)
	{weight: 0.06, template: ScenarioTemplate{
		ScenarioType: "no_package_placed", DeliveryStatus: "failed",
		DeliveryLocation: "unknown", RiskScoreMin: 0.50, RiskScoreMax: 0.70,
		RiskFactors: []string{"no_package_detected", "door_opened_unnecessarily", "possible_missed_delivery"},
		AlertType:   "no_package",
		Description: "Garage door opened but no package was placed inside",
		Events: []EventTemplate{
			{"delivery_window_start", "garage", 0, 0, "", 0},
			{"person_detected", "driveway", 1800, 7200, "delivery_driver", 0.87},
			{"door_open", "garage", 5, 15, "", 0},
			{"camera_motion", "garage", 1, 3, "person", 0.85},
			{"package_not_detected", "garage", 30, 60, "", 0},
			{"door_close", "garage", 5, 15, "", 0},
		},
	}},
	// 6. Delivery Timeout (5%)
	{weight: 0.05, template: ScenarioTemplate{
		ScenarioType: "delivery_timeout", DeliveryStatus: "failed",
		DeliveryLocation: "unknown", RiskScoreMin: 0.30, RiskScoreMax: 0.50,
		RiskFactors: []string{"delivery_not_received", "window_expired", "no_carrier_activity"},
		AlertType:   "delivery_timeout",
		Description: "Expected delivery window passed with no delivery activity",
		Events: []EventTemplate{
			{"delivery_window_start", "garage", 0, 0, "", 0},
			{"delivery_window_end", "garage", 14400, 14400, "", 0},
			{"delivery_timeout", "garage", 900, 1800, "", 0},
		},
	}},
	// 7. Theft / Suspicious Activity (3%)
	{weight: 0.03, template: ScenarioTemplate{
		ScenarioType: "theft_suspicious", DeliveryStatus: "suspicious",
		DeliveryLocation: "front_door", RiskScoreMin: 0.85, RiskScoreMax: 0.98,
		RiskFactors: []string{"package_theft_risk", "unknown_person_detected", "package_may_be_stolen", "suspicious_activity_after_delivery"},
		AlertType:   "theft_risk",
		Description: "Package delivered to front door, then suspicious person detected near it",
		Events: []EventTemplate{
			{"delivery_window_start", "garage", 0, 0, "", 0},
			{"person_detected", "driveway", 1800, 7200, "delivery_driver", 0.90},
			{"camera_motion", "front_door", 15, 40, "person", 0.88},
			{"package_detected", "front_door", 5, 15, "package", 0.92},
			{"camera_motion", "front_door", 300, 1800, "person", 0.79},
			{"unknown_person", "front_door", 1, 5, "unknown_person", 0.85},
		},
	}},
}

func PickScenario() ScenarioTemplate {
	total := 0.0
	for _, ws := range scenarios {
		total += ws.weight
	}
	r := rand.Float64() * total
	cum := 0.0
	for _, ws := range scenarios {
		cum += ws.weight
		if r <= cum {
			return ws.template
		}
	}
	return scenarios[0].template
}
