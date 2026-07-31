"""Generate the synthetic municipal disclosure corpus and its extraction ground truth."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen.canvas import Canvas

from src.corpus.manifest import (
    CorpusManifest,
    DefectKind,
    DocumentEntry,
    DocumentType,
    PlantedDefect,
)
from src.domain.entities.deal import (
    CallProvision,
    Deal,
    Issuer,
    MaturityTranche,
    RatingSet,
    SecurityType,
    Sensitivity,
)

DEAL_TEAM_GROUP = "deal-team-private-side"
SYNTHETIC_NOTICE = (
    "SYNTHETIC DEMONSTRATION DOCUMENT. The issuer and all figures are fictional. "
    "No content was derived from MSRB EMMA or another disclosure system."
)


@dataclass(frozen=True)
class _Section:
    heading: str
    paragraphs: tuple[str, ...]


@dataclass(frozen=True)
class _CorpusDocument:
    document_id: str
    title: str
    document_type: DocumentType
    deal: Deal
    sections: tuple[_Section, ...]
    sensitivity: Sensitivity = Sensitivity.PUBLIC
    allowed_group_claims: tuple[str, ...] = ()
    defects: tuple[PlantedDefect, ...] = ()
    include_maturity_schedule: bool = False


class _PdfDocument:
    """Small PDF writer whose explicit pagination makes manifest page counts reliable."""

    def __init__(self, path: Path, title: str, sensitivity: Sensitivity) -> None:
        self._canvas = Canvas(str(path), pagesize=LETTER, pageCompression=1)
        self._title = title
        self._sensitivity = sensitivity
        self._width, self._height = LETTER
        self._left = 0.7 * inch
        self._right = self._width - 0.7 * inch
        self._top = self._height - 0.65 * inch
        self._bottom = 0.65 * inch
        self._y = self._top
        self.page_count = 1
        self._draw_header()

    def _draw_header(self) -> None:
        self._canvas.setFillColor(colors.HexColor("#123B54"))
        self._canvas.rect(0, self._height - 0.35 * inch, self._width, 0.35 * inch, fill=1)
        self._canvas.setFillColor(colors.white)
        self._canvas.setFont("Helvetica-Bold", 8)
        label = f"MUNICIPAL DEAL DESK | {self._sensitivity.value.upper()}"
        self._canvas.drawString(self._left, self._height - 0.23 * inch, label)
        self._canvas.setFillColor(colors.black)

    def _draw_footer(self) -> None:
        self._canvas.setStrokeColor(colors.HexColor("#B8C4CA"))
        self._canvas.line(self._left, 0.48 * inch, self._right, 0.48 * inch)
        self._canvas.setFont("Helvetica", 7)
        self._canvas.setFillColor(colors.HexColor("#52636B"))
        self._canvas.drawString(self._left, 0.32 * inch, "Synthetic demo corpus")
        self._canvas.drawRightString(
            self._right, 0.32 * inch, f"Page {self.page_count} | {self._title}"
        )

    def _new_page(self) -> None:
        self._draw_footer()
        self._canvas.showPage()
        self.page_count += 1
        self._y = self._top
        self._draw_header()

    def _ensure_space(self, height: float) -> None:
        if self._y - height < self._bottom:
            self._new_page()

    def title(self, text: str) -> None:
        lines = simpleSplit(text, "Helvetica-Bold", 18, self._right - self._left)
        height = len(lines) * 22 + 8
        self._ensure_space(height)
        self._canvas.setFillColor(colors.HexColor("#123B54"))
        self._canvas.setFont("Helvetica-Bold", 18)
        for line in lines:
            self._canvas.drawString(self._left, self._y, line)
            self._y -= 22
        self._canvas.setFillColor(colors.black)
        self._y -= 8

    def heading(self, text: str) -> None:
        self._ensure_space(24)
        self._canvas.setFillColor(colors.HexColor("#B14C2E"))
        self._canvas.setFont("Helvetica-Bold", 11)
        self._canvas.drawString(self._left, self._y, text.upper())
        self._canvas.setFillColor(colors.black)
        self._y -= 17

    def paragraph(self, text: str, *, emphasis: bool = False) -> None:
        font = "Helvetica-Bold" if emphasis else "Helvetica"
        size = 8.5 if emphasis else 9
        lines = simpleSplit(text, font, size, self._right - self._left)
        height = len(lines) * 12 + 7
        self._ensure_space(height)
        self._canvas.setFont(font, size)
        for line in lines:
            self._canvas.drawString(self._left, self._y, line)
            self._y -= 12
        self._y -= 7

    def key_values(self, values: tuple[tuple[str, str], ...]) -> None:
        row_height = 15
        self._ensure_space(len(values) * row_height + 5)
        for index, (label, value) in enumerate(values):
            if index % 2 == 0:
                self._canvas.setFillColor(colors.HexColor("#EDF2F4"))
                self._canvas.rect(
                    self._left - 3,
                    self._y - 3,
                    self._right - self._left + 6,
                    row_height,
                    fill=1,
                    stroke=0,
                )
            self._canvas.setFillColor(colors.HexColor("#263940"))
            self._canvas.setFont("Helvetica-Bold", 8)
            self._canvas.drawString(self._left, self._y, label)
            self._canvas.setFont("Helvetica", 8)
            self._canvas.drawString(self._left + 1.75 * inch, self._y, value)
            self._y -= row_height
        self._canvas.setFillColor(colors.black)
        self._y -= 5

    def maturity_schedule(self, maturities: list[MaturityTranche]) -> None:
        self.heading("Serial Maturity Schedule")
        headers = ("Maturity", "Principal", "Coupon", "Yield")
        x_positions = (
            self._left,
            self._left + 1.45 * inch,
            self._left + 3.25 * inch,
            self._left + 4.45 * inch,
        )
        self._ensure_space(18)
        self._canvas.setFillColor(colors.HexColor("#123B54"))
        self._canvas.rect(self._left - 3, self._y - 4, self._right - self._left + 6, 15, fill=1)
        self._canvas.setFillColor(colors.white)
        self._canvas.setFont("Helvetica-Bold", 8)
        for x_position, header in zip(x_positions, headers, strict=True):
            self._canvas.drawString(x_position, self._y, header)
        self._y -= 17
        for maturity in maturities:
            self._ensure_space(14)
            values = (
                maturity.maturity_date.strftime("%B %d, %Y"),
                f"${maturity.principal_amount:,.0f}",
                f"{maturity.coupon_rate:.2f}%",
                f"{maturity.yield_rate:.2f}%" if maturity.yield_rate is not None else "N/A",
            )
            self._canvas.setFillColor(colors.black)
            self._canvas.setFont("Helvetica", 8)
            for x_position, value in zip(x_positions, values, strict=True):
                self._canvas.drawString(x_position, self._y, value)
            self._y -= 14
        self._y -= 5

    def save(self) -> int:
        self._draw_footer()
        self._canvas.save()
        return self.page_count


def _maturities(par_amount: Decimal, dated_date: date, deal_index: int) -> list[MaturityTranche]:
    principal = par_amount / Decimal("10")
    base_coupon = Decimal("4.00") + Decimal(deal_index) * Decimal("0.05")
    return [
        MaturityTranche(
            maturity_date=date(dated_date.year + offset + 1, 8, 15),
            principal_amount=principal,
            coupon_rate=base_coupon + Decimal(offset - 1) * Decimal("0.10"),
            yield_rate=base_coupon + Decimal(offset - 1) * Decimal("0.08") - Decimal("0.05"),
        )
        for offset in range(1, 11)
    ]


def _deal(
    index: int,
    issuer_name: str,
    county: str,
    enrollment: int,
    par_millions: int,
    dated_date: date,
    *,
    call_provision: CallProvision | None,
    sensitivity: Sensitivity = Sensitivity.PUBLIC,
    source_document_id: str,
) -> Deal:
    par_amount = Decimal(par_millions) * Decimal("1000000")
    maturities = _maturities(par_amount, dated_date, index)
    ratings = (
        RatingSet(moodys="Aa1", sp="AAA", is_enhanced=True)
        if index % 2
        else RatingSet(moodys="Aa2", sp="AAA", is_enhanced=True)
    )
    return Deal(
        deal_id=f"DEAL-{index:03d}",
        issuer=Issuer(
            issuer_id=f"FICT-ISD-{index:03d}",
            name=issuer_name,
            state="TX",
            county=county,
            enrollment=enrollment,
            taxable_assessed_valuation=Decimal(par_millions * 75) * Decimal("1000000"),
        ),
        series_name=f"Unlimited Tax School Building Bonds, Series {dated_date.year}",
        security_type=SecurityType.UNLIMITED_TAX,
        par_amount=par_amount,
        dated_date=dated_date,
        first_maturity=maturities[0].maturity_date,
        final_maturity=maturities[-1].maturity_date,
        ratings=ratings,
        call_provision=call_provision,
        maturities=maturities,
        sensitivity=sensitivity,
        source_document_id=source_document_id,
    )


def _call(year: int) -> CallProvision:
    return CallProvision(first_call_date=date(year, 8, 15), call_price=Decimal("100.00"))


def _official_statement_documents() -> list[_CorpusDocument]:
    issuers = (
        ("Blue Mesa Fictional Independent School District", "Travis", 8_420, 30, date(2025, 2, 18)),
        (
            "Cedar Prairie Fictional Independent School District",
            "Denton",
            11_760,
            45,
            date(2025, 4, 15),
        ),
        (
            "Copper Star Fictional Independent School District",
            "Williamson",
            15_200,
            60,
            date(2025, 6, 17),
        ),
        (
            "Juniper Bend Fictional Independent School District",
            "Collin",
            9_680,
            75,
            date(2025, 8, 19),
        ),
        (
            "Lone Heron Fictional Independent School District",
            "Fort Bend",
            18_940,
            90,
            date(2025, 11, 18),
        ),
        (
            "North Lantern Fictional Independent School District",
            "Hays",
            12_840,
            105,
            date(2026, 2, 17),
        ),
        (
            "Red Bluff Fictional Independent School District",
            "Bexar",
            22_300,
            120,
            date(2026, 5, 19),
        ),
        (
            "Silver Cactus Fictional Independent School District",
            "Tarrant",
            27_450,
            150,
            date(2026, 7, 14),
        ),
    )
    documents: list[_CorpusDocument] = []
    for index, (issuer_name, county, enrollment, par_millions, pricing_date) in enumerate(
        issuers, start=1
    ):
        document_id = f"OS-{index:03d}"
        dated_date = date(pricing_date.year, pricing_date.month, 15)
        call_provision = None if index == 3 else _call(max(2033, dated_date.year + 8))
        deal = _deal(
            index,
            issuer_name,
            county,
            enrollment,
            par_millions,
            dated_date,
            call_provision=call_provision,
            source_document_id=document_id,
        )
        defects: list[PlantedDefect] = []
        if index == 3:
            defects.append(
                PlantedDefect(
                    kind=DefectKind.MISSING_CALL_PROVISION,
                    description="The official statement contains no redemption terms.",
                    expected_behaviour=(
                        "State that the call provision is unavailable and do not infer a call date "
                        "or price."
                    ),
                )
            )
        if index == 6:
            defects.append(
                PlantedDefect(
                    kind=DefectKind.CONFLICTING_FIGURE,
                    description=("Enrollment is 12,840 here but 13,215 in annual report CD-001."),
                    expected_behaviour=(
                        "Surface both cited enrollment figures as a conflict and require review "
                        "before using either figure."
                    ),
                    related_document_id="CD-001",
                )
            )
        if index == 8:
            defects.append(
                PlantedDefect(
                    kind=DefectKind.STALE_FINANCIALS,
                    description=(
                        "The July 2026 statement presents audited financials only through "
                        "August 31, 2023."
                    ),
                    expected_behaviour=(
                        "Flag the financial information as stale and do not present it as current."
                    ),
                )
            )
        call_text = (
            "No optional redemption or call provision is stated in this document."
            if call_provision is None
            else (
                f"Bonds maturing on or after {call_provision.first_call_date:%B %d, %Y} are "
                f"redeemable at {call_provision.call_price:.2f}% of par plus accrued interest."
            )
        )
        financial_period = "August 31, 2023" if index == 8 else "August 31, 2025"
        documents.append(
            _CorpusDocument(
                document_id=document_id,
                title=f"Official Statement - {issuer_name} - Series {dated_date.year}",
                document_type=DocumentType.OFFICIAL_STATEMENT,
                deal=deal,
                include_maturity_schedule=True,
                defects=tuple(defects),
                sections=(
                    _Section(
                        "Offering Summary",
                        (
                            f"Pricing date: {pricing_date:%B %d, %Y}. The bonds are unlimited "
                            "tax school building bonds payable from an unlimited ad valorem tax "
                            "levied by the fictional district.",
                            f"The district reports enrollment of {enrollment:,} students.",
                        ),
                    ),
                    _Section("Ratings", (_ratings_text(deal.ratings),)),
                    _Section("Optional Redemption", (call_text,)),
                    _Section(
                        "Financial Information",
                        (
                            f"The latest audited financial statements included are for the fiscal "
                            f"year ended {financial_period}.",
                        ),
                    ),
                ),
            )
        )
    return documents


def _ratings_text(ratings: RatingSet) -> str:
    enhancement = " with Texas Permanent School Fund enhancement" if ratings.is_enhanced else ""
    return f"Moody's: {ratings.moodys}; S&P: {ratings.sp}{enhancement}."


def _related_document(
    source: _CorpusDocument,
    *,
    document_id: str,
    title: str,
    document_type: DocumentType,
    sections: tuple[_Section, ...],
    enrollment: int | None = None,
    sensitivity: Sensitivity = Sensitivity.PUBLIC,
    allowed_group_claims: tuple[str, ...] = (),
    defects: tuple[PlantedDefect, ...] = (),
) -> _CorpusDocument:
    issuer = source.deal.issuer.model_copy(
        update={
            "enrollment": enrollment if enrollment is not None else source.deal.issuer.enrollment
        }
    )
    deal = source.deal.model_copy(
        update={
            "issuer": issuer,
            "sensitivity": sensitivity,
            "source_document_id": document_id,
        }
    )
    return _CorpusDocument(
        document_id=document_id,
        title=title,
        document_type=document_type,
        deal=deal,
        sections=sections,
        sensitivity=sensitivity,
        allowed_group_claims=allowed_group_claims,
        defects=defects,
    )


def _disclosure_documents(official_statements: list[_CorpusDocument]) -> list[_CorpusDocument]:
    north_lantern = official_statements[5]
    conflict = PlantedDefect(
        kind=DefectKind.CONFLICTING_FIGURE,
        description="Enrollment is 13,215 here but 12,840 in official statement OS-006.",
        expected_behaviour=(
            "Surface both cited enrollment figures as a conflict and require review before using "
            "either figure."
        ),
        related_document_id="OS-006",
    )
    annual_one = _related_document(
        north_lantern,
        document_id="CD-001",
        title="Annual Continuing Disclosure - North Lantern Fictional ISD - FY2025",
        document_type=DocumentType.CONTINUING_DISCLOSURE,
        enrollment=13_215,
        defects=(conflict,),
        sections=(
            _Section(
                "Annual Update",
                (
                    "This annual report updates operating and debt information for the fiscal "
                    "year ended August 31, 2025.",
                    "Enrollment for the 2025-2026 school year is reported as 13,215 students.",
                    "Filing deadline: February 28, 2026. Filing date: February 20, 2026.",
                ),
            ),
        ),
    )
    late_defect = PlantedDefect(
        kind=DefectKind.LATE_DISCLOSURE,
        description="The annual filing was due February 28, 2026 and filed April 17, 2026.",
        expected_behaviour=(
            "Flag the filing as late, cite the due and filing dates, and route the finding for "
            "compliance review."
        ),
    )
    annual_two = _related_document(
        official_statements[3],
        document_id="CD-002",
        title="Annual Continuing Disclosure - Juniper Bend Fictional ISD - FY2025",
        document_type=DocumentType.CONTINUING_DISCLOSURE,
        defects=(late_defect,),
        sections=(
            _Section(
                "Annual Update",
                (
                    "This annual report updates operating and debt information for the fiscal "
                    "year ended August 31, 2025.",
                    "Enrollment for the 2025-2026 school year is 9,680 students.",
                    "Filing deadline: February 28, 2026. Filing date: April 17, 2026.",
                ),
            ),
        ),
    )
    event_notice = _related_document(
        official_statements[1],
        document_id="ME-001",
        title="Material Event Notice - Cedar Prairie Fictional ISD",
        document_type=DocumentType.MATERIAL_EVENT_NOTICE,
        sections=(
            _Section(
                "Event Notice",
                (
                    "On June 12, 2026, the fictional district was notified that its underlying "
                    "Moody's rating changed from Aa1 to Aa2. The enhanced S&P rating remains AAA.",
                    "This notice is synthetic and is supplied only to exercise event retrieval.",
                ),
            ),
        ),
    )
    return [annual_one, annual_two, event_notice]


def _pricing_memos(official_statements: list[_CorpusDocument]) -> list[_CorpusDocument]:
    documents: list[_CorpusDocument] = []
    for memo_index, source_index in enumerate((0, 4, 6), start=1):
        source = official_statements[source_index]
        documents.append(
            _related_document(
                source,
                document_id=f"PM-{memo_index:03d}",
                title=f"Internal Pricing Memo - {source.deal.issuer.name}",
                document_type=DocumentType.INTERNAL_PRICING_MEMO,
                sensitivity=Sensitivity.PRIVATE,
                allowed_group_claims=(DEAL_TEAM_GROUP,),
                sections=(
                    _Section(
                        "Deal Team Pricing View",
                        (
                            "PRIVATE-SIDE DEAL TEAM MATERIAL. Do not distribute outside the "
                            "authorized deal-team group.",
                            f"Working view: price {source.deal.series_name} against fictional "
                            "Texas PSF-enhanced school district comparables, with additional "
                            "attention to call structure and enrollment trend.",
                            "This memo contains synthetic assumptions for entitlement testing; "
                            "it is not an offer, recommendation, or record of an actual trade.",
                        ),
                    ),
                ),
            )
        )
    return documents


def _deal_summary(deal: Deal) -> tuple[tuple[str, str], ...]:
    call_value = "Not stated"
    if deal.call_provision is not None and deal.call_provision.first_call_date is not None:
        call_value = (
            f"{deal.call_provision.first_call_date:%B %d, %Y} at "
            f"{deal.call_provision.call_price:.2f}%"
        )
    return (
        ("Issuer", deal.issuer.name),
        ("Series", deal.series_name),
        ("Security", "Unlimited Tax School Building Bonds"),
        ("Par Amount", f"${deal.par_amount:,.0f}"),
        ("Dated Date", deal.dated_date.strftime("%B %d, %Y") if deal.dated_date else "N/A"),
        ("Enrollment", f"{deal.issuer.enrollment:,}" if deal.issuer.enrollment else "N/A"),
        ("Ratings", _ratings_text(deal.ratings)),
        ("Call Provision", call_value),
    )


def _render(document: _CorpusDocument, path: Path) -> int:
    pdf = _PdfDocument(path, document.title, document.sensitivity)
    pdf.title(document.title)
    pdf.paragraph(SYNTHETIC_NOTICE, emphasis=True)
    pdf.heading("Document Ground Truth")
    pdf.key_values(_deal_summary(document.deal))
    for section in document.sections:
        pdf.heading(section.heading)
        for paragraph in section.paragraphs:
            pdf.paragraph(paragraph)
    if document.include_maturity_schedule:
        pdf.maturity_schedule(document.deal.maturities)
    return pdf.save()


def generate_corpus(output_dir: Path | None = None) -> CorpusManifest:
    """Generate all PDFs and return the manifest written beside them."""
    destination = output_dir or Path(__file__).resolve().parent / "out"
    destination.mkdir(parents=True, exist_ok=True)
    for generated_file in (*destination.glob("*.pdf"), destination / "manifest.json"):
        generated_file.unlink(missing_ok=True)

    official_statements = _official_statement_documents()
    documents = [
        *official_statements,
        *_disclosure_documents(official_statements),
        *_pricing_memos(official_statements),
    ]
    entries: list[DocumentEntry] = []
    for document in documents:
        filename = f"{document.document_id.lower()}.pdf"
        page_count = _render(document, destination / filename)
        entries.append(
            DocumentEntry(
                document_id=document.document_id,
                title=document.title,
                document_type=document.document_type,
                sensitivity=document.sensitivity,
                blob_path=filename,
                page_count=page_count,
                allowed_group_claims=list(document.allowed_group_claims),
                expected_deal=document.deal,
                defects=list(document.defects),
            )
        )

    manifest = CorpusManifest(
        generated_at=datetime.now(UTC).isoformat(),
        documents=entries,
    )
    (destination / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Destination directory. Defaults to src/corpus/out.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = generate_corpus(args.output_dir)
    print(f"Generated {len(manifest.documents)} PDFs and manifest.json")


if __name__ == "__main__":
    main()
