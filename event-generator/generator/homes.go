package generator

import (
	"fmt"
	"math/rand"
	"smart-delivery/event-generator/models"
)

var suburbs = []struct {
	City string
	Zip  string
}{
	{"Naperville", "60540"}, {"Oak Brook", "60523"}, {"Schaumburg", "60173"},
	{"Evanston", "60201"}, {"Wheaton", "60187"}, {"Downers Grove", "60515"},
	{"Arlington Heights", "60004"}, {"Plainfield", "60544"}, {"Bolingbrook", "60440"},
	{"Lake Forest", "60045"}, {"Highland Park", "60035"}, {"Hinsdale", "60521"},
	{"Glen Ellyn", "60137"}, {"Libertyville", "60048"}, {"Geneva", "60134"},
	{"Oswego", "60543"}, {"Woodridge", "60517"}, {"Lisle", "60532"},
	{"Wilmette", "60091"}, {"Barrington", "60010"}, {"St. Charles", "60174"},
	{"Batavia", "60510"}, {"Elmhurst", "60126"}, {"Western Springs", "60558"},
	{"La Grange", "60525"}, {"Park Ridge", "60068"}, {"Glenview", "60025"},
	{"Northbrook", "60062"}, {"Buffalo Grove", "60089"}, {"Vernon Hills", "60061"},
}

var streetNames = []string{
	"Oak", "Maple", "Cedar", "Elm", "Pine", "Birch", "Walnut", "Cherry",
	"Willow", "Hickory", "Ash", "Sycamore", "Poplar", "Spruce", "Magnolia",
}
var streetTypes = []string{
	"Street", "Avenue", "Drive", "Lane", "Court", "Way", "Boulevard", "Terrace",
	"Place", "Circle", "Trail", "Parkway",
}
var firstNames = []string{
	"James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
	"David", "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica",
	"Thomas", "Sarah", "Charles", "Karen", "Daniel", "Lisa", "Matthew", "Nancy",
	"Anthony", "Betty", "Mark", "Margaret", "Steven", "Sandra", "Paul", "Ashley",
	"Andrew", "Kimberly", "Joshua", "Emily", "Kenneth", "Donna", "Kevin", "Michelle",
}
var lastNames = []string{
	"Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
	"Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
	"Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
	"White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
}
var firmwares = []string{"3.2.1", "3.2.0", "3.1.4", "3.1.3", "3.0.9"}

func randHex(n int) string {
	const hex = "0123456789abcdef"
	b := make([]byte, n)
	for i := range b {
		b[i] = hex[rand.Intn(16)]
	}
	return string(b)
}

func GenerateHomes(count int) []models.Home {
	homes := make([]models.Home, count)
	for i := 0; i < count; i++ {
		sub := suburbs[rand.Intn(len(suburbs))]
		streetNum := 100 + rand.Intn(9900)
		street := streetNames[rand.Intn(len(streetNames))]
		stype := streetTypes[rand.Intn(len(streetTypes))]
		first := firstNames[rand.Intn(len(firstNames))]
		last := lastNames[rand.Intn(len(lastNames))]

		homeID := fmt.Sprintf("home-%04d", i+1)
		fw := firmwares[rand.Intn(len(firmwares))]

		devices := []models.DeviceInfo{
			{DeviceID: fmt.Sprintf("GDO-SEN-%s", randHex(4)), Type: "garage_door_sensor", Location: "garage", Firmware: fw},
			{DeviceID: fmt.Sprintf("CAM-GAR-%s", randHex(4)), Type: "garage_camera", Location: "garage", Firmware: fw},
			{DeviceID: fmt.Sprintf("CAM-FRT-%s", randHex(4)), Type: "front_door_camera", Location: "front_door", Firmware: fw},
		}
		hasFrontLock := rand.Float64() < 0.7
		if hasFrontLock {
			devices = append(devices, models.DeviceInfo{
				DeviceID: fmt.Sprintf("LCK-FRT-%s", randHex(4)), Type: "front_door_lock", Location: "front_door", Firmware: fw,
			})
		}

		tier := "premium"
		if rand.Float64() < 0.25 {
			tier = "basic"
		}
		numDoors := 1
		if rand.Float64() < 0.25 {
			numDoors = 2
		}

		homes[i] = models.Home{
			ID:                 homeID,
			Address:            fmt.Sprintf("%d %s %s", streetNum, street, stype),
			City:               sub.City,
			State:              "IL",
			ZipCode:            sub.Zip,
			OwnerName:          fmt.Sprintf("%s %s", first, last),
			Devices:            devices,
			SubscriptionTier:   tier,
			HasGarageCamera:    true,
			HasFrontDoorCamera: true,
			NumGarageDoors:     numDoors,
			Latitude:           41.7 + rand.Float64()*0.35,
			Longitude:          -88.3 + rand.Float64()*0.5,
		}
	}
	return homes
}
