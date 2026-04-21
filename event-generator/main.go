package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"math/rand"
	"os"
	"os/signal"
	"sync"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/couchbase/gocb/v2"

	"smart-delivery/event-generator/config"
	cbclient "smart-delivery/event-generator/couchbase"
	"smart-delivery/event-generator/generator"
	"smart-delivery/event-generator/models"
)

func main() {
	numHomes := flag.Int("homes", 200, "Number of homes to generate")
	numScenarios := flag.Int("scenarios", 50, "Number of delivery scenarios to generate")
	continuous := flag.Bool("continuous", false, "Run in continuous mode (stream events)")
	rate := flag.Int("rate", 100, "Target deliveries/sec in continuous mode")
	duration := flag.Duration("duration", 0, "Duration for continuous mode (0 = until stopped)")
	workers := flag.Int("workers", 40, "Number of writer goroutines in continuous mode")
	batchSize := flag.Int("batch", 100, "Batch size for collection.Do() bulk writes")
	maxCount := flag.Int("count", 0, "Max deliveries to generate in continuous mode (0 = unlimited)")
	flag.Parse()

	// Load config
	cfg := config.Load()
	if cfg.ConnStr == "" {
		fmt.Fprintln(os.Stderr, "ERROR: CB_CONN_STR not set. Check ../.env file.")
		os.Exit(1)
	}

	// Connect to Couchbase
	fmt.Println("=== SmartDelivery Event Generator ===")
	fmt.Println("[1/5] Connecting to Couchbase...")
	client, err := cbclient.Connect(cfg)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Connection failed: %v\n", err)
		os.Exit(1)
	}
	defer client.Close()
	fmt.Println("      Connected!")

	if *continuous {
		// Generate homes in-memory only (used by delivery producer for realistic addresses)
		homes := generator.GenerateHomes(200)

		runContinuousFast(client, *rate, *duration, *workers, *batchSize, *maxCount, homes)
		return
	}

	// ── Batch mode (original) ──
	fmt.Printf("Scenarios: %d\n\n", *numScenarios)

	// Generate homes in-memory only (used for realistic addresses in deliveries)
	fmt.Println("[1/3] Generating homes in memory...")
	homes := generator.GenerateHomes(*numHomes)
	fmt.Printf("      Generated %d homes (in-memory only, not written to Couchbase)\n", len(homes))

	// Generate delivery scenarios
	fmt.Printf("[2/3] Generating %d delivery scenarios...\n", *numScenarios)
	allEvents := make(map[string]interface{})
	allDeliveries := make(map[string]interface{})
	allAlerts := make(map[string]interface{})

	eventSeq := 1
	statusCounts := map[string]int{}

	for i := 0; i < *numScenarios; i++ {
		home := homes[rand.Intn(len(homes))]
		tmpl := generator.PickScenario()

		baseTime := time.Now().UTC().Add(-time.Duration(rand.Intn(7*24)) * time.Hour)
		baseTime = baseTime.Add(-time.Duration(rand.Intn(3600)) * time.Second)

		events := generator.BuildEvents(tmpl, home, baseTime, eventSeq)
		eventSeq += len(events)

		for _, e := range events {
			allEvents[e.ID] = e
		}

		delivery, alert := generator.BuildDelivery(i, home, tmpl, events)
		allDeliveries[delivery.ID] = delivery
		statusCounts[delivery.Status]++

		if alert != nil {
			allAlerts[alert.ID] = alert
		}
	}

	fmt.Println("      Distribution:")
	for status, count := range statusCounts {
		pct := float64(count) / float64(*numScenarios) * 100
		fmt.Printf("        %-20s %3d (%5.1f%%)\n", status, count, pct)
	}

	fmt.Printf("[3/3] Writing %d events...\n", len(allEvents))
	ec, err := client.BulkUpsert("events", allEvents)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to upsert events: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("      Wrote %d events\n", ec)

	fmt.Printf("      Writing %d deliveries...\n", len(allDeliveries))
	dc, err := client.BulkUpsert("deliveries", allDeliveries)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to upsert deliveries: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("      Wrote %d deliveries\n", dc)

	fmt.Printf("      Writing %d alerts...\n", len(allAlerts))
	ac, err := client.BulkUpsert("alerts", allAlerts)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to upsert alerts: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("      Wrote %d alerts\n", ac)

	fmt.Println()
	fmt.Println("Summary:")
	fmt.Printf("      Events:     %d\n", ec)
	fmt.Printf("      Deliveries: %d\n", dc)
	fmt.Printf("      Alerts:     %d\n", ac)
	fmt.Println()

	fmt.Println("=== Done! Raw data loaded into rawdata.* collections ===")
}

// ── Fast Continuous mode (producer-consumer with collection.Do() bulk API) ──

// Metrics holds live pipeline metrics written to Couchbase for the UI
type Metrics struct {
	TotalEventsIngested int64   `json:"total_events_ingested"`
	TotalDeliveries     int64   `json:"total_deliveries"`
	TotalAlerts         int64   `json:"total_alerts"`
	TargetRate          int     `json:"target_rate"`
	ActualRate          float64 `json:"actual_rate"`
	StartTime           string  `json:"start_time"`
	LastUpdate          string  `json:"last_update"`
	Running             bool    `json:"running"`
	ElapsedSeconds      float64 `json:"elapsed_seconds"`
	Workers             int     `json:"workers"`
	BatchSize           int     `json:"batch_size"`
}

// bulkDoc is a document waiting to be written, with its collection target
type bulkDoc struct {
	collection string // "events", "deliveries", or "alerts"
	key        string
	value      interface{}
}

func runContinuousFast(client *cbclient.Client, targetRate int, maxDuration time.Duration, numWorkers int, batchSize int, maxDeliveries int, homes []models.Home) {
	fmt.Println()
	fmt.Println("=== High-Performance Continuous Event Stream ===")
	fmt.Printf("Target rate:    %d deliveries/sec\n", targetRate)
	fmt.Printf("Workers:        %d\n", numWorkers)
	fmt.Printf("Batch size:     %d (collection.Do() bulk API)\n", batchSize)
	if maxDeliveries > 0 {
		fmt.Printf("Max deliveries: %d\n", maxDeliveries)
	}
	if maxDuration > 0 {
		fmt.Printf("Duration:       %v\n", maxDuration)
	} else if maxDeliveries == 0 {
		fmt.Println("Duration:       until Ctrl+C")
	}
	fmt.Println()

	// Context with cancellation for graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Signal handler for Ctrl+C
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-sigChan
		fmt.Println("\n\nReceived interrupt signal. Shutting down gracefully...")
		cancel()
	}()

	// Timer-based duration limit
	if maxDuration > 0 {
		go func() {
			time.Sleep(maxDuration)
			cancel()
		}()
	}

	var metrics Metrics
	metrics.TargetRate = targetRate
	metrics.Workers = numWorkers
	metrics.BatchSize = batchSize
	metrics.StartTime = time.Now().UTC().Format(time.RFC3339)
	metrics.Running = true

	startTime := time.Now()

	// Write initial metrics
	writeMetrics(client, &metrics)

	// Document channel: producer -> consumers (buffered for throughput)
	docChan := make(chan bulkDoc, numWorkers*batchSize*2)

	// ── Producer goroutine: generates deliveries and feeds docs into channel ──
	var eventsThisSecond int64
	go func() {
		defer close(docChan)

		deliverySeq := int64(time.Now().UnixNano() / 1000000)
		interval := time.Second / time.Duration(targetRate)
		throttle := time.NewTicker(interval)
		defer throttle.Stop()

		for {
			select {
			case <-ctx.Done():
				return
			case <-throttle.C:
				home := homes[rand.Intn(len(homes))]
				tmpl := generator.PickScenario()
				now := time.Now().UTC()

				events := generator.BuildEvents(tmpl, home, now, int(deliverySeq))
				delivery, alert := generator.BuildDelivery(int(deliverySeq), home, tmpl, events)
				deliverySeq++

				// Feed events into channel
				for _, e := range events {
					select {
					case docChan <- bulkDoc{collection: "events", key: e.ID, value: e}:
						atomic.AddInt64(&eventsThisSecond, 1)
					case <-ctx.Done():
						return
					}
				}

				// Feed delivery
				select {
				case docChan <- bulkDoc{collection: "deliveries", key: delivery.ID, value: delivery}:
				case <-ctx.Done():
					return
				}
				atomic.AddInt64(&metrics.TotalDeliveries, 1)

				// Auto-stop when delivery limit is reached
				if maxDeliveries > 0 && atomic.LoadInt64(&metrics.TotalDeliveries) >= int64(maxDeliveries) {
					fmt.Printf("\n\nReached delivery limit (%d). Auto-stopping...\n", maxDeliveries)
					cancel()
					return
				}
				// Feed alert if any
				if alert != nil {
					select {
					case docChan <- bulkDoc{collection: "alerts", key: alert.ID, value: alert}:
					case <-ctx.Done():
						return
					}
					atomic.AddInt64(&metrics.TotalAlerts, 1)
				}
			}
		}
	}()

	// ── Consumer workers: batch docs and write via collection.Do() ──
	var wg sync.WaitGroup
	var totalInserted int64
	var totalErrors int64

	for w := 0; w < numWorkers; w++ {
		wg.Add(1)
		go func(workerID int) {
			defer wg.Done()

			batch := make([]bulkDoc, 0, batchSize)
			// Group by collection for efficient bulk writes
			collectionOps := map[string][]gocb.BulkOp{}

			flushBatch := func() {
				if len(batch) == 0 {
					return
				}

				// Group by collection
				for _, doc := range batch {
					ops, ok := collectionOps[doc.collection]
					if !ok {
						ops = make([]gocb.BulkOp, 0, batchSize)
					}
					ops = append(ops, &gocb.UpsertOp{
						ID:    doc.key,
						Value: doc.value,
					})
					collectionOps[doc.collection] = ops
				}

				// Execute bulk writes per collection
				for colName, ops := range collectionOps {
					col := client.Raw.Collection(colName)
					for attempt := 0; attempt < 3; attempt++ {
						err := col.Do(ops, nil)
						if err == nil {
							succeeded := int64(0)
							for _, op := range ops {
								uop := op.(*gocb.UpsertOp)
								if uop.Err == nil {
									succeeded++
								} else {
									atomic.AddInt64(&totalErrors, 1)
								}
							}
							atomic.AddInt64(&totalInserted, succeeded)
							break
						}
						// Retry with backoff
						time.Sleep(time.Duration(attempt+1) * 100 * time.Millisecond)
					}
				}

				// Reset
				batch = batch[:0]
				for k := range collectionOps {
					delete(collectionOps, k)
				}
			}

			for {
				select {
				case doc, ok := <-docChan:
					if !ok {
						// Channel closed - flush remaining
						flushBatch()
						return
					}
					batch = append(batch, doc)
					if len(batch) >= batchSize {
						flushBatch()
					}
				case <-time.After(100 * time.Millisecond):
					// Flush partial batches periodically to avoid stalling
					flushBatch()
				case <-ctx.Done():
					flushBatch()
					return
				}
			}
		}(w)
	}

	// ── Stats reporter goroutine ──
	ticker := time.NewTicker(1 * time.Second)
	go func() {
		for {
			select {
			case <-ctx.Done():
				ticker.Stop()
				return
			case <-ticker.C:
				count := atomic.SwapInt64(&eventsThisSecond, 0)
				elapsed := time.Since(startTime).Seconds()
				metrics.TotalEventsIngested += count
				metrics.ActualRate = float64(count)
				metrics.ElapsedSeconds = elapsed
				metrics.LastUpdate = time.Now().UTC().Format(time.RFC3339)
				inserted := atomic.LoadInt64(&totalInserted)
				errors := atomic.LoadInt64(&totalErrors)
				writeMetrics(client, &metrics)
				fmt.Printf("\r  [%6.0fs] Rate: %6d ops/sec | Inserted: %8d | Errors: %d | Deliveries: %d | Alerts: %d",
					elapsed, count, inserted, errors, atomic.LoadInt64(&metrics.TotalDeliveries), atomic.LoadInt64(&metrics.TotalAlerts))
			}
		}
	}()

	// Wait for all workers to finish
	wg.Wait()

	// Final stats
	metrics.Running = false
	metrics.LastUpdate = time.Now().UTC().Format(time.RFC3339)
	writeMetrics(client, &metrics)

	elapsed := time.Since(startTime).Seconds()
	inserted := atomic.LoadInt64(&totalInserted)
	errors := atomic.LoadInt64(&totalErrors)

	fmt.Println()
	fmt.Println()
	fmt.Println("=== Continuous stream stopped ===")
	fmt.Printf("Total inserted:  %d docs\n", inserted)
	fmt.Printf("Total errors:    %d\n", errors)
	fmt.Printf("Deliveries:      %d\n", atomic.LoadInt64(&metrics.TotalDeliveries))
	fmt.Printf("Alerts:          %d\n", atomic.LoadInt64(&metrics.TotalAlerts))
	fmt.Printf("Duration:        %.0f seconds\n", elapsed)
	if elapsed > 0 {
		fmt.Printf("Average rate:    %.0f ops/sec\n", float64(inserted)/elapsed)
	}
	fmt.Printf("Workers:         %d\n", numWorkers)
	fmt.Printf("Batch size:      %d\n", batchSize)
}

func writeMetrics(client *cbclient.Client, m *Metrics) {
	col := client.Raw.Collection("events")
	b, err := json.Marshal(m)
	if err != nil {
		return
	}
	var raw json.RawMessage = b
	col.Upsert("pipeline_metrics", raw, nil)
}
