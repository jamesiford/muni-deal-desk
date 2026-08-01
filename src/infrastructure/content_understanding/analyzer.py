"""Content Understanding analyzer definition and idempotent registration."""

from __future__ import annotations

from collections.abc import Mapping

from azure.ai.contentunderstanding.models import (
    ContentAnalyzer,
    ContentAnalyzerConfig,
    ContentFieldDefinition,
    ContentFieldSchema,
    ContentFieldType,
    GenerationMethod,
)
from azure.core.exceptions import HttpResponseError

ANALYZER_ID = "municipal_deal_extraction"


def _contains(current: object, desired: object) -> bool:
    if isinstance(desired, Mapping):
        return isinstance(current, Mapping) and all(
            key in current and _contains(current[key], value) for key, value in desired.items()
        )
    if isinstance(desired, list):
        return (
            isinstance(current, list)
            and len(current) == len(desired)
            and all(_contains(left, right) for left, right in zip(current, desired, strict=True))
        )
    return current == desired


def _field_names_match(current: object, desired: object) -> bool:
    """Require exact extraction field sets while tolerating server-added defaults."""
    if not isinstance(current, Mapping) or not isinstance(desired, Mapping):
        return False
    current_fields = current.get("fields")
    desired_fields = desired.get("fields")
    if not isinstance(current_fields, Mapping) or not isinstance(desired_fields, Mapping):
        return False
    if set(current_fields) != set(desired_fields):
        return False
    for name, desired_field in desired_fields.items():
        current_field = current_fields[name]
        if not isinstance(current_field, Mapping) or not isinstance(desired_field, Mapping):
            continue
        desired_properties = desired_field.get("properties")
        if desired_properties is not None:
            current_properties = current_field.get("properties")
            if not isinstance(current_properties, Mapping) or not isinstance(
                desired_properties, Mapping
            ):
                return False
            if set(current_properties) != set(desired_properties):
                return False
    return True


def ensure_model_defaults(client: object, desired: dict[str, str]) -> str:
    """Set resource model defaults only when missing or different."""
    try:
        current = client.get_defaults()  # type: ignore[attr-defined]
    except HttpResponseError as exc:
        if "DefaultsNotSet" not in str(exc):
            raise
        client.update_defaults(model_deployments=desired)  # type: ignore[attr-defined]
        return "created"

    if current.model_deployments == desired:
        return "unchanged"
    client.update_defaults(model_deployments=desired)  # type: ignore[attr-defined]
    return "updated"


def _field(
    field_type: ContentFieldType,
    description: str,
    *,
    enum: list[str] | None = None,
    item_definition: ContentFieldDefinition | None = None,
    properties: dict[str, ContentFieldDefinition] | None = None,
) -> ContentFieldDefinition:
    return ContentFieldDefinition(
        type=field_type,
        method=GenerationMethod.EXTRACT,
        description=description,
        enum=enum,
        item_definition=item_definition,
        properties=properties,
        estimate_source_and_confidence=True,
    )


def build_deal_analyzer(
    *,
    completion_model: str,
    embedding_model: str,
) -> ContentAnalyzer:
    """Build the durable analyzer used for municipal deal documents."""
    string = ContentFieldType.STRING
    number = ContentFieldType.NUMBER
    date = ContentFieldType.DATE
    boolean = ContentFieldType.BOOLEAN

    maturity = _field(
        ContentFieldType.OBJECT,
        "One maturity row from the debt service schedule.",
        properties={
            "maturity_date": _field(date, "Maturity date."),
            "principal_amount": _field(number, "Principal amount due."),
            "coupon_rate": _field(number, "Coupon rate as a percent."),
            "yield_rate": _field(number, "Yield rate as a percent, when stated."),
        },
    )
    schema = ContentFieldSchema(
        name="municipal_deal",
        description="Typed new-issue terms extracted from a municipal document.",
        fields={
            "issuer": _field(
                ContentFieldType.OBJECT,
                "Municipal issuer details.",
                properties={
                    "name": _field(string, "Full issuer name."),
                    "state": _field(string, "Two-letter state code."),
                    "county": _field(string, "County, when stated."),
                    "enrollment": _field(number, "Student enrollment, when stated."),
                    "taxable_assessed_valuation": _field(
                        number, "Taxable assessed valuation, when stated."
                    ),
                },
            ),
            "series_name": _field(string, "Full bond series name."),
            "security_type": _field(
                string,
                "Normalized security pledge.",
                enum=[
                    "unlimited_tax",
                    "limited_tax",
                    "revenue",
                    "certificate_of_obligation",
                ],
            ),
            "par_amount": _field(number, "Aggregate par amount in dollars."),
            "dated_date": _field(date, "Dated date."),
            "first_maturity": _field(date, "First maturity date."),
            "final_maturity": _field(date, "Final maturity date."),
            "ratings": _field(
                ContentFieldType.OBJECT,
                "Issue ratings exactly as stated.",
                properties={
                    "moodys": _field(string, "Moody's rating."),
                    "sp": _field(string, "S&P rating."),
                    "fitch": _field(string, "Fitch rating."),
                    "enhancement": _field(
                        string,
                        "Normalize the stated rating basis.",
                        enum=["enhanced", "not_enhanced"],
                    ),
                },
            ),
            "call_provision": _field(
                ContentFieldType.OBJECT,
                "Optional redemption terms. Omit when the document does not state them.",
                properties={
                    "first_call_date": _field(date, "First optional redemption date."),
                    "call_price": _field(number, "Call price as percent of par."),
                    "is_non_callable": _field(boolean, "Whether the issue is non-callable."),
                },
            ),
            "maturities": _field(
                ContentFieldType.ARRAY,
                "All maturity rows and coupons.",
                item_definition=maturity,
            ),
        },
    )
    return ContentAnalyzer(
        base_analyzer_id="prebuilt-document",
        description="Extracts typed terms from the synthetic Municipal Deal Desk corpus.",
        config=ContentAnalyzerConfig(
            enable_layout=True,
            enable_ocr=True,
            estimate_field_source_and_confidence=True,
            return_details=True,
        ),
        field_schema=schema,
        models={"completion": completion_model, "embedding": embedding_model},
    )


def ensure_deal_analyzer(client: object, desired: ContentAnalyzer) -> str:
    """Create or replace the named analyzer only when its definition changed."""
    try:
        current = client.get_analyzer(analyzer_id=ANALYZER_ID)  # type: ignore[attr-defined]
    except Exception as exc:
        if getattr(exc, "status_code", None) != 404:
            raise
        client.begin_create_analyzer(  # type: ignore[attr-defined]
            analyzer_id=ANALYZER_ID,
            resource=desired,
        ).result()
        return "created"

    current_dict = current.as_dict()
    desired_dict = desired.as_dict()
    field_names_match = _field_names_match(
        current_dict.get("fieldSchema"), desired_dict.get("fieldSchema")
    )
    if field_names_match and _contains(current_dict, desired_dict):
        return "unchanged"

    if not field_names_match:
        client.delete_analyzer(analyzer_id=ANALYZER_ID)  # type: ignore[attr-defined]
        client.begin_create_analyzer(  # type: ignore[attr-defined]
            analyzer_id=ANALYZER_ID,
            resource=desired,
        ).result()
        return "replaced"

    client.update_analyzer(  # type: ignore[attr-defined]
        analyzer_id=ANALYZER_ID,
        resource=desired,
    )
    return "updated"
