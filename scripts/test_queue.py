import sys
from nad_ch.config.development_local import create_app_context
from nad_ch.infrastructure.task_queue import load_and_validate

try:
    ctx = create_app_context()
    print(f"Broker: {ctx._task_queue.app.conf.broker_url}")
    print(f"Backend: {ctx._task_queue.app.conf.result_backend}")
    print("Testing apply_async...")
    result = load_and_validate.apply_async(args=[1, "test_path", {}, "test_dir"])
    print(f"Task ID: {result.id}")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
