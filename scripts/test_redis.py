# scripts/test_redis.py
import redis
import sys

def test_conn(host, port):
    print(f"Testing connection to {host}:{port}...")
    try:
        r = redis.Redis(host=host, port=port, socket_connect_timeout=2)
        r.ping()
        print(f"[PASS] Connected to {host}:{port}")
        return True
    except Exception as e:
        print(f"[FAIL] Failed to connect to {host}:{port}: {e}")
        return False

if __name__ == "__main__":
    success = test_conn("localhost", 6379)
    success &= test_conn("127.0.0.1", 6379)
    
    if not success:
        sys.exit(1)
