package models

type Alert struct {
	ID              string   `json:"id"`
	DeliveryID      string   `json:"delivery_id"`
	HomeID          string   `json:"home_id"`
	Address         string   `json:"address"`
	AlertType       string   `json:"alert_type"`
	Severity        string   `json:"severity"`
	Message         string   `json:"message"`
	TriggeredAt     string   `json:"triggered_at"`
	Acknowledged    bool     `json:"acknowledged"`
	RelatedEventIDs []string `json:"related_event_ids"`
}
