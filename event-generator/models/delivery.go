package models

type TimelineEntry struct {
	EventID   string `json:"event_id"`
	EventType string `json:"event_type"`
	Location  string `json:"location"`
	Summary   string `json:"summary"`
	Timestamp string `json:"timestamp"`
}

type Delivery struct {
	ID                  string          `json:"id"`
	HomeID              string          `json:"home_id"`
	Address             string          `json:"address"`
	OwnerName           string          `json:"owner_name"`
	Status              string          `json:"status"`
	ScenarioType        string          `json:"scenario_type"`
	Carrier             string          `json:"carrier"`
	ExpectedWindowStart string          `json:"expected_window_start"`
	ExpectedWindowEnd   string          `json:"expected_window_end"`
	ActualDeliveryTime  string          `json:"actual_delivery_time,omitempty"`
	DeliveryLocation    string          `json:"delivery_location"`
	EventIDs            []string        `json:"event_ids"`
	EventTimeline       []TimelineEntry `json:"event_timeline"`
	RiskScore           float64         `json:"risk_score"`
	RiskFactors         []string        `json:"risk_factors"`
	CreatedAt           string          `json:"created_at"`
	UpdatedAt           string          `json:"updated_at"`
	ProcessingStatus    string          `json:"processing_status"`
}
