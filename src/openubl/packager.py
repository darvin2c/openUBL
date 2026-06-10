"""
ZIP packaging for SUNAT electronic documents.
Based on Manual del Programador SUNAT (RS N° 097-2012/SUNAT).

Nomenclatura ZIP:
- Factura/Notas: {RUC}-{tipo}-{serie}-{numero}.ZIP
- VoidedDocuments: {RUC}-RA-{YYYYMMDD}-{numero}.ZIP
- SummaryDocuments: {RUC}-RC-{YYYYMMDD}-{numero}.ZIP
- Perception: {RUC}-40-{serie}-{numero}.ZIP
- Retention: {RUC}-20-{serie}-{numero}.ZIP

Contenido ZIP:
- dummy/ (directorio vacío)
- {nombre}.xml
"""
import io
import zipfile
from datetime import date


def build_filename(ruc: str, tipo_comprobante: str, serie: str, numero: int) -> str:
    """Build SUNAT filename without extension."""
    return f"{ruc}-{tipo_comprobante}-{serie}-{numero}"


def _create_zip(xml_string: str, filename: str) -> bytes:
    """Create ZIP with dummy/ dir + XML file."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("dummy/", "")
        zf.writestr(f"{filename}.xml", xml_string)
    return zip_buffer.getvalue()


def package_invoice(xml_string: str, ruc: str, tipo_comprobante: str, serie: str, numero: int) -> bytes:
    """Package invoice XML into SUNAT ZIP."""
    filename = build_filename(ruc, tipo_comprobante, serie, numero)
    return _create_zip(xml_string, filename)


def package_voided_documents(xml_string: str, ruc: str, fecha: date, numero: int) -> bytes:
    """Package voided documents XML into SUNAT ZIP."""
    filename = f"{ruc}-RA-{fecha.strftime('%Y%m%d')}-{numero}"
    return _create_zip(xml_string, filename)


def package_summary_documents(xml_string: str, ruc: str, fecha: date, numero: int) -> bytes:
    """Package summary documents XML into SUNAT ZIP."""
    filename = f"{ruc}-RC-{fecha.strftime('%Y%m%d')}-{numero}"
    return _create_zip(xml_string, filename)


def package_perception(xml_string: str, ruc: str, serie: str, numero: int) -> bytes:
    """Package perception XML into SUNAT ZIP."""
    filename = build_filename(ruc, "40", serie, numero)
    return _create_zip(xml_string, filename)


def package_retention(xml_string: str, ruc: str, serie: str, numero: int) -> bytes:
    """Package retention XML into SUNAT ZIP."""
    filename = build_filename(ruc, "20", serie, numero)
    return _create_zip(xml_string, filename)
