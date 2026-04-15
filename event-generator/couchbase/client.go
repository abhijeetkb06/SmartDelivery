package couchbase

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/couchbase/gocb/v2"

	"smart-delivery/event-generator/config"
)

type Client struct {
	cluster *gocb.Cluster
	bucket  *gocb.Bucket
	Raw     *gocb.Scope
}

func Connect(cfg config.Config) (*Client, error) {
	opts := gocb.ClusterOptions{
		Authenticator: gocb.PasswordAuthenticator{
			Username: cfg.Username,
			Password: cfg.Password,
		},
		SecurityConfig: gocb.SecurityConfig{
			TLSSkipVerify: true,
		},
	}

	cluster, err := gocb.Connect(cfg.ConnStr, opts)
	if err != nil {
		return nil, fmt.Errorf("connect: %w", err)
	}
	if err := cluster.WaitUntilReady(60*time.Second, nil); err != nil {
		return nil, fmt.Errorf("wait ready: %w", err)
	}

	bucket := cluster.Bucket(cfg.Bucket)
	if err := bucket.WaitUntilReady(30*time.Second, nil); err != nil {
		return nil, fmt.Errorf("bucket ready: %w", err)
	}

	raw := bucket.Scope("rawdata")

	return &Client{cluster: cluster, bucket: bucket, Raw: raw}, nil
}

func (c *Client) Close() {
	c.cluster.Close(nil)
}

func (c *Client) BulkUpsert(collectionName string, docs map[string]interface{}) (int, error) {
	col := c.Raw.Collection(collectionName)
	count := 0
	for id, doc := range docs {
		b, err := json.Marshal(doc)
		if err != nil {
			return count, fmt.Errorf("marshal %s: %w", id, err)
		}
		var raw json.RawMessage = b
		_, err = col.Upsert(id, raw, nil)
		if err != nil {
			return count, fmt.Errorf("upsert %s: %w", id, err)
		}
		count++
	}
	return count, nil
}
