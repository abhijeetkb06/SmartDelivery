package models

type DeviceInfo struct {
	DeviceID string `json:"device_id"`
	Type     string `json:"type"`
	Location string `json:"location"`
	Firmware string `json:"firmware"`
}

type Home struct {
	ID                 string       `json:"id"`
	Address            string       `json:"address"`
	City               string       `json:"city"`
	State              string       `json:"state"`
	ZipCode            string       `json:"zip_code"`
	OwnerName          string       `json:"owner_name"`
	Devices            []DeviceInfo `json:"devices"`
	SubscriptionTier   string       `json:"subscription_tier"`
	HasGarageCamera    bool         `json:"has_garage_camera"`
	HasFrontDoorCamera bool         `json:"has_front_door_camera"`
	NumGarageDoors     int          `json:"num_garage_doors"`
	Latitude           float64      `json:"latitude"`
	Longitude          float64      `json:"longitude"`
}
