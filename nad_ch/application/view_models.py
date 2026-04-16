from dataclasses import dataclass
from datetime import datetime
import json
import numpy as np
from typing import Union, Dict, List, Tuple, Protocol
from nad_ch.core.entities import (
    Entity,
    ColumnMap,
    DataProducer,
    DataSubmissionStatus,
    DataSubmission,
)


class ViewModel(Protocol):
    pass


def get_view_model(
    entity: Union[Entity, List[Entity]],
) -> Union[ViewModel, List[ViewModel]]:
    """
    Provide a single factory function that an application use case can call in order to
    get a static view model object that it can return to its caller.
    """
    entity_to_vm_function_map = {
        ColumnMap: create_column_map_view_model,
        DataProducer: create_data_producer_vm,
        DataSubmission: create_data_submission_vm,
    }

    # Check if the input is a list of entities
    if isinstance(entity, list):
        # Process each entity in the list using a list comprehension
        return [get_view_model(single_entity) for single_entity in entity]

    # Process a single entity
    entity_type = type(entity)
    if entity_type in entity_to_vm_function_map:
        mapping_function = entity_to_vm_function_map[entity_type]
        return mapping_function(entity)  # Call the mapping function for the entity
    else:
        raise ValueError(f"No mapping function defined for entity type: {entity_type}")


@dataclass
class ColumnMapViewModel(ViewModel):
    id: int
    date_created: str
    date_updated: str
    name: str
    mapping: Dict[str, str]
    version: int
    producer_name: str
    available_nad_fields: List[str]
    required_nad_fields: List[str]


def create_column_map_view_model(column_map: ColumnMap) -> ColumnMapViewModel:
    available_nad_fields = [
        key
        for key in ColumnMap.all_fields
        if key not in column_map.mapping or column_map.mapping.get(key) in ["", None]
    ]

    date_updated = (
        "-"
        if column_map.updated_at == column_map.created_at
        and column_map.updated_at is not None
        else present_date(column_map.updated_at)
    )

    return ColumnMapViewModel(
        id=column_map.id,
        date_created=present_date(column_map.created_at),
        date_updated=date_updated,
        name=column_map.name,
        mapping=column_map.mapping,
        version=column_map.version_id,
        producer_name=column_map.producer.name,
        available_nad_fields=available_nad_fields,
        required_nad_fields=ColumnMap.required_fields,
    )


@dataclass
class DataProducerViewModel(ViewModel):
    id: int
    date_created: str
    name: str


def create_data_producer_vm(producer: DataProducer) -> DataProducerViewModel:
    return DataProducerViewModel(
        id=producer.id,
        date_created=present_date(producer.created_at),
        name=producer.name,
    )


@dataclass
class DataSubmissionViewModel(ViewModel):
    id: int
    date_created: str
    name: str
    status: str
    status_tag_class: str
    producer_name: str
    file_path: str
    report: str
    column_map_name: str
    column_map_version: int
    mapped_data_path: str
    mapped_data_gdb_path: str


def create_data_submission_vm(submission: DataSubmission) -> DataSubmissionViewModel:
    report_json = []
    if submission.report is not None:
        report_json = enrich_report(submission.report)

    status_map = {
        DataSubmissionStatus.PENDING_SUBMISSION: "Pending submission",
        DataSubmissionStatus.CANCELED: "Canceled",
        DataSubmissionStatus.PENDING_VALIDATION: "Pending validation",
        DataSubmissionStatus.FAILED: "Validation failed",
        DataSubmissionStatus.VALIDATED: "Validated",
    }

    status_tag_class_map = {
        DataSubmissionStatus.PENDING_SUBMISSION: "usa-tag__warning",
        DataSubmissionStatus.CANCELED: "usa-tag__error",
        DataSubmissionStatus.PENDING_VALIDATION: "usa-tag__warning",
        DataSubmissionStatus.FAILED: "usa-tag__error",
        DataSubmissionStatus.VALIDATED: "usa-tag__success",
    }

    return DataSubmissionViewModel(
        id=submission.id,
        date_created=present_date(submission.created_at),
        name=submission.name,
        status=status_map[submission.status],
        status_tag_class=status_tag_class_map[submission.status],
        producer_name=submission.producer.name,
        file_path=submission.file_path,
        report=report_json,
        column_map_name=submission.column_map.name,
        column_map_version=submission.column_map.version_id,
        mapped_data_path=submission.mapped_data_path or "",
        mapped_data_gdb_path=submission.mapped_data_gdb_path or "",
    )


def enrich_report(report: dict) -> dict:
    overview = report.get("overview", {})
    total_records = overview.get("records_count", 0)

    for feature in report.get("features", []):
        null_count = feature.get("null_count", 0)
        populated_count = feature.get("populated_count", 0)

        if total_records > 0:
            percent_populated = (populated_count / total_records) * 100
            percent_empty = (null_count / total_records) * 100
        else:
            percent_populated, percent_empty = 0.0, 0.0

        feature["populated_percentage"] = present_percentage(percent_populated)
        feature["null_percentage"] = present_percentage(percent_empty)

        # Set status
        if populated_count == 0:
            feature["status"] = "Empty"
        elif populated_count == total_records:
            feature["status"] = "Populated"
        else:
            feature["status"] = "Partially Populated"

    return report


def present_date(date: datetime) -> str:
    return date.strftime("%B %d, %Y")


def calculate_percentages(populated_count: int, null_count: int) -> Tuple[float, float]:
    total_fields = populated_count + null_count
    populated_percentage = (populated_count / total_fields) * 100
    null_percentage = (null_count / total_fields) * 100
    return populated_percentage, null_percentage


def present_percentage(percentage: float) -> str:
    rounded_percentage = np.around(percentage, 2)
    formatted_string = (
        f"{rounded_percentage:05.2f}%" if rounded_percentage != 0 else "00.00%"
    )
    return formatted_string
