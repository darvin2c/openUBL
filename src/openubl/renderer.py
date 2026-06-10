"""
Template rendering engine for UBL 2.1 XML documents.
"""
from jinja2 import Environment, PackageLoader, select_autoescape


env = Environment(
    loader=PackageLoader("openubl", "templates"),
    autoescape=select_autoescape(["xml"]),
)


def render_invoice(doc) -> str:
    """Render an Invoice to XML."""
    template = env.get_template("invoice.xml.j2")
    return template.render(doc=doc)


def render_credit_note(doc) -> str:
    """Render a CreditNote to XML."""
    template = env.get_template("credit_note.xml.j2")
    return template.render(doc=doc)


def render_debit_note(doc) -> str:
    """Render a DebitNote to XML."""
    template = env.get_template("debit_note.xml.j2")
    return template.render(doc=doc)


def render_voided_documents(doc) -> str:
    """Render VoidedDocuments to XML."""
    template = env.get_template("voided_documents.xml.j2")
    return template.render(doc=doc)


def render_summary_documents(doc) -> str:
    """Render SummaryDocuments to XML."""
    template = env.get_template("summary_documents.xml.j2")
    return template.render(doc=doc)


def render_perception(doc) -> str:
    """Render Perception to XML."""
    template = env.get_template("perception.xml.j2")
    return template.render(doc=doc)


def render_retention(doc) -> str:
    """Render Retention to XML."""
    template = env.get_template("retention.xml.j2")
    return template.render(doc=doc)
