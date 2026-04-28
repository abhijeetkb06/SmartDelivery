#!/usr/bin/env bash
# Reset SmartDelivery: delete bucket entirely, then run full setup from scratch.
# Usage: ./reset_bucket.sh

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== SmartDelivery Bucket Reset ==="
echo ""

# Step 0: Kill the Go event generator if it's running
BINARY="smart-delivery-gen"
PIDS=$(pgrep -f "${BINARY}" 2>/dev/null || true)
if [ -n "${PIDS}" ]; then
    echo "Stopping running event generator..."
    pkill -9 -f "${BINARY}" 2>/dev/null || true
    sleep 1
    echo "  Generator stopped."
else
    echo "No running event generator found."
fi
echo ""

# Step 1: Undeploy + drop eventing, then delete bucket via Capella API
cd "$PROJECT_DIR" && python -c "
import os, time, requests
from dotenv import load_dotenv
from datetime import timedelta
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.management.eventing import EventingFunctionState

load_dotenv()

# ── Undeploy and drop eventing functions first ──
print('Step 1: Cleaning up eventing functions...')
try:
    cluster = Cluster(
        os.getenv('CB_CONN_STR'),
        ClusterOptions(PasswordAuthenticator(os.getenv('CB_USERNAME'), os.getenv('CB_PASSWORD')))
    )
    cluster.wait_until_ready(timedelta(seconds=10))
    eventing_mgr = cluster.eventing_functions()
    for fn in ('DeliveryKnowledgePipeline', 'VectorEmbeddingPipeline'):
        try:
            eventing_mgr.undeploy_function(fn)
        except Exception:
            pass
    # Wait for undeploy
    for _ in range(15):
        time.sleep(2)
        status = eventing_mgr.functions_status()
        if all(f.state == EventingFunctionState.Undeployed for f in status.functions):
            break
    for fn in ('DeliveryKnowledgePipeline', 'VectorEmbeddingPipeline'):
        try:
            eventing_mgr.drop_function(fn)
            print(f'  Dropped: {fn}')
        except Exception:
            pass
except Exception as e:
    print(f'  Eventing cleanup skipped: {e}')

# ── Delete bucket via Capella Management API ──
print('Step 2: Deleting bucket via Capella API...')
base = os.getenv('CAPELLA_API_BASE', 'https://cloudapi.cloud.couchbase.com')
headers = {
    'Authorization': 'Bearer ' + os.getenv('CAPELLA_API_SECRET', ''),
    'Content-Type': 'application/json',
}

orgs = requests.get(f'{base}/v4/organizations', headers=headers, timeout=30).json()
org_id = orgs['data'][0]['id']

projects = requests.get(f'{base}/v4/organizations/{org_id}/projects', headers=headers, timeout=30).json()
project_id = projects['data'][0]['id']

clusters = requests.get(f'{base}/v4/organizations/{org_id}/projects/{project_id}/clusters', headers=headers, timeout=30).json()
conn_host = os.getenv('CB_CONN_STR', '').replace('couchbases://', '')
cluster_id = None
for c in clusters['data']:
    if conn_host in c.get('connectionString', ''):
        cluster_id = c['id']
        break
if not cluster_id:
    cluster_id = clusters['data'][0]['id']

bp = f'/v4/organizations/{org_id}/projects/{project_id}/clusters/{cluster_id}'

bucket_name = os.getenv('CB_BUCKET', 'smartdelivery')
buckets = requests.get(f'{base}{bp}/buckets', headers=headers, timeout=30).json()
bucket_id = None
for b in buckets.get('data', []):
    if b.get('name') == bucket_name:
        bucket_id = b.get('id', bucket_name)
        break

if bucket_id:
    r = requests.delete(f'{base}{bp}/buckets/{bucket_id}', headers=headers, timeout=30)
    if r.status_code in (200, 202, 204):
        print(f'  Bucket deleted.')
    else:
        print(f'  Delete response: {r.status_code} {r.text}')
    print('  Waiting for bucket deletion...')
    time.sleep(10)
else:
    print(f'  Bucket not found (already deleted).')
"

# Step 2: Run full setup (creates bucket, scopes, collections, indexes, eventing)
echo ""
echo "Step 3: Running full setup..."
cd "$PROJECT_DIR" && python scripts/setup_couchbase.py

echo ""
echo "=== Reset complete! Bucket recreated from scratch. ==="
