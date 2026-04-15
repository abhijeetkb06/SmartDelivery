package config

import (
	"bufio"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

type Config struct {
	ConnStr  string
	Username string
	Password string
	Bucket   string
}

func Load() Config {
	// Try loading ../.env relative to the binary or working directory
	candidates := []string{
		filepath.Join("..", ".env"),
		".env",
	}
	// Also try relative to source file
	_, filename, _, ok := runtime.Caller(0)
	if ok {
		candidates = append(candidates, filepath.Join(filepath.Dir(filename), "..", "..", ".env"))
	}

	env := map[string]string{}
	for _, path := range candidates {
		if f, err := os.Open(path); err == nil {
			scanner := bufio.NewScanner(f)
			for scanner.Scan() {
				line := strings.TrimSpace(scanner.Text())
				if line == "" || strings.HasPrefix(line, "#") {
					continue
				}
				parts := strings.SplitN(line, "=", 2)
				if len(parts) == 2 {
					env[strings.TrimSpace(parts[0])] = strings.TrimSpace(parts[1])
				}
			}
			f.Close()
			break
		}
	}

	return Config{
		ConnStr:  getEnv(env, "CB_CONN_STR"),
		Username: getEnv(env, "CB_USERNAME"),
		Password: getEnv(env, "CB_PASSWORD"),
		Bucket:   getEnv(env, "CB_BUCKET"),
	}
}

func getEnv(env map[string]string, key string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return env[key]
}
