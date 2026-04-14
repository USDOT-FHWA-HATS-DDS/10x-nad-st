import os
from nad_ch.config.development_local import (
    DevLocalApplicationContext as dev_local_app_context,
)
from nad_ch.config.development_remote import (
    DevRemoteApplicationContext as dev_remote_app_context,
)
from celery import Celery
from nad_ch.application.dtos import (
    DataSubmissionReport,
    report_to_dict,
    report_from_dict,
)
from nad_ch.application.data_handler import DataHandler
from nad_ch.application.interfaces import TaskQueue
from nad_ch.application.validation import DataValidator
from nad_ch.config import QUEUE_BROKER_URL, QUEUE_BACKEND_URL
from nad_ch.core.repositories import DataSubmissionRepository
from datetime import datetime, timezone
from typing import Dict, Any
from nad_ch.core.entities import DataSubmissionStatus


celery_app = Celery(
    "redis-task-queue",
    broker=QUEUE_BROKER_URL,
    backend=QUEUE_BACKEND_URL,
    broker_connection_retry=True,  # Enable broker connection retry
    broker_connection_retry_delay=5,  # Optional: retry delay in seconds
    broker_connection_retry_max=3,  # Optional: maximum number of retries
    broker_connection_retry_on_startup=True,  # Enable retry on startup
)


celery_app.conf.update(
    task_concurrency=4,
    store_processed=True,
    result_persistent=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)


@celery_app.task(bind=True, max_retries=2)
def load_and_validate(
    self,
    submission_id: int,
    file_path: str,
    column_map: Dict[str, str],
    mapped_data_dir: str,
) -> Any:
    import os
    os.environ["SHAPE_RESTORE_SHX"] = "YES"

    app_context = TaskHelperFunctions.get_app_context_instance()
    app_context.logger.info(f"Task load_and_validate started for submission {submission_id}")
    app_context.logger.info(f"  file_path: {file_path}")
    app_context.logger.info(f"  mapped_data_dir: {mapped_data_dir}")
    temp_dir = None
    try:
        storage = app_context.create_storage()
        download_result = storage.download_temp(file_path)
        if not download_result:
            raise Exception(f"Failed to download file from storage: {file_path}")

        temp_dir = download_result.temp_dir
        gdb_file_path = download_result.extracted_dir
        app_context.logger.info(f"  extracted_dir: {gdb_file_path}")

        data_handler = DataHandler(column_map, mapped_data_dir)
        batch_count = 0
        for gdf in data_handler.read_file_in_batches(path=gdb_file_path):
            batch_count += 1
            if batch_count == 1:
                data_validator = DataValidator(data_handler.valid_renames)
            data_validator.run(gdf)

        data_validator.finalize_overview_details()
        report = DataSubmissionReport(
            data_validator.report_overview,
            list(data_validator.report_features.values()),
        )
        report_dict = report_to_dict(report)

        app_context.submissions.update_report(submission_id, report_dict)
        app_context.logger.info(f"Task load_and_validate completed for submission {submission_id}. Batches: {batch_count}")

        return report_dict
    except Exception as e:
        app_context.logger.error(f"Task load_and_validate failed for submission {submission_id}: {e}")
        try:
            self.retry(exc=e, countdown=30)
        except self.MaxRetriesExceededError:
            app_context = TaskHelperFunctions.get_app_context_instance()
            app_context.submissions.update_status(
                submission_id, DataSubmissionStatus.FAILED
            )
            raise e
    finally:
        if temp_dir and os.path.exists(temp_dir):
            import shutil
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                app_context = TaskHelperFunctions.get_app_context_instance()
                app_context.logger.warning(f"Failed to cleanup temp dir {temp_dir}: {e}")


@celery_app.task(bind=True, max_retries=2)
def copy_mapped_data_to_remote(
    self, mapped_data_local_dir: str, mapped_data_remote_dir: str
) -> bool:
    try:
        success = True
        app_context = TaskHelperFunctions.get_app_context_instance()
        storage_interface = app_context.create_storage()
        filename = mapped_data_remote_dir.split("/")[-1]
        timestamp = datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M%S")
        # Copy mapped dataset to remote storage
        storage_interface.upload(
            os.path.join(mapped_data_local_dir, f"{filename}.zip"),
            os.path.join(mapped_data_remote_dir, f"{filename}_{timestamp}.zip"),
        )
    except Exception as e:
        raise self.retry(exc=e, countdown=30)
    finally:
        # Clean up temporary directory after processing
        if mapped_data_local_dir and os.path.exists(mapped_data_local_dir):
            import shutil
            try:
                shutil.rmtree(mapped_data_local_dir)
            except Exception as e:
                # Log cleanup error but don't fail the task
                app_context = TaskHelperFunctions.get_app_context_instance()
                app_context.logger.warning(f"Failed to cleanup temp dir {mapped_data_local_dir}: {e}")
    return success


class CeleryTaskQueue(TaskQueue):
    def __init__(self, app):
        self.app = app

    def run_load_and_validate(
        self,
        submissions: DataSubmissionRepository,
        submission_id: int,
        file_path: str,
        column_map: Dict[str, str],
        mapped_data_dir: str,
    ):
        result = load_and_validate.apply_async(args=[submission_id, file_path, column_map, mapped_data_dir])
        app_context = TaskHelperFunctions.get_app_context_instance()
        app_context.logger.info(f"DEBUG: Task load_and_validate enqueued with ID: {result.id} to broker {load_and_validate.app.conf.broker_url}")
        return True

    def run_copy_mapped_data_to_remote(
        self,
        mapped_data_dir: str,
        mapped_data_remote_dir: str,
    ):
        copy_mapped_data_to_remote.apply_async(
            args=[mapped_data_dir, mapped_data_remote_dir]
        )
        return True


class TaskHelperFunctions:

    @staticmethod
    def get_app_context_instance():
        APP_ENV = os.environ.get("APP_ENV")
        if APP_ENV == "dev_local":
            from nad_ch.config.development_local import create_app_context
        elif APP_ENV == "dev_remote":
            from nad_ch.config.development_remote import create_app_context
        elif APP_ENV == "test":
            from nad_ch.config.test import create_app_context

        return create_app_context()
