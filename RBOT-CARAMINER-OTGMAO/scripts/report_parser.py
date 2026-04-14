# -*- coding: utf-8 -*-
from rp_helpers.rp_io import (
    configure_output_encoding,
    load_report_read,
    write_output_file,
)
from rp_helpers.rp_parser_core import (
    build_output_dictionary,
    build_report_body_text,
    build_work_orders_dictionary,
    calculate_counts,
    extract_report_metadata,
    validate_metadata_required_fields,
)
from rp_helpers.rp_patterns import ReportStructureError, ensure_structure


def main():
    configure_output_encoding()

    report_read = load_report_read()
    ensure_structure(isinstance(report_read, list), "STRUCTURE_ERROR: parsed report must be a list")
    ensure_structure(len(report_read) > 0, "STRUCTURE_ERROR: parsed report is empty")

    metadata, report_name = extract_report_metadata(report_read)
    validate_metadata_required_fields(metadata)
    text = build_report_body_text(report_read)
    wo_dictionary = build_work_orders_dictionary(text)

    counts = calculate_counts(wo_dictionary)
    work_order_dictionary = build_output_dictionary(metadata, counts, wo_dictionary)

    output_file_path = write_output_file(work_order_dictionary, report_name)
    return output_file_path


def run():
    try:
        return main()
    except ReportStructureError as exc:
        raise RuntimeError(f"STRUCTURE_PHASE_ERROR: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"RUNTIME_PHASE_ERROR: {exc}") from exc

if __name__ == "__main__":
    print(run())