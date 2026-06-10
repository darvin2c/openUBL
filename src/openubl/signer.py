"""
XML Digital Signing for SUNAT electronic documents.
Uses signxml for pure-Python XML signing.

RS N° 300-2014/SUNAT, Anexo 1 - Firma Digital:
- Certificado X.509
- Algoritmo RSA-SHA1
- Signature dentro de UBLExtension

Note: SUNAT requires RSA-SHA1 which signxml 4.x blocks by default.
We temporarily disable the deprecated method check to support SUNAT's
required signature algorithm.
"""
from lxml import etree
from signxml import XMLSigner
from signxml.signer import XMLSigner as _XMLSigner

# SUNAT requires RSA-SHA1; signxml 4.x blocks it by default.
# This is a known requirement for Peruvian electronic invoicing.
_XMLSigner.check_deprecated_methods = lambda self: None


def sign_ubl_xml(
    xml_string: str,
    cert_pem: str,
    key_pem: str,
    signature_id: str = "SignSUNAT",
) -> str:
    """Sign a UBL XML document and place signature inside ExtensionContent."""
    root = etree.fromstring(xml_string.encode("utf-8"))

    signer = XMLSigner(
        c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315",
        digest_algorithm="sha1",
        signature_algorithm="rsa-sha1",
    )
    signed_root = signer.sign(root, key=key_pem, cert=cert_pem)

    ns = {
        "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
        "ds": "http://www.w3.org/2000/09/xmldsig#",
    }
    sig = signed_root.xpath("//ds:Signature", namespaces=ns)[0]
    sig.attrib["Id"] = signature_id
    ext_content = signed_root.xpath(
        "//ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent",
        namespaces=ns,
    )[0]
    ext_content.append(sig)

    return etree.tostring(
        signed_root,
        xml_declaration=True,
        encoding="UTF-8",
        pretty_print=True,
    ).decode("utf-8")


def load_pfx(pfx_bytes: bytes, password: str) -> tuple[str, str]:
    """Extract key and cert PEM from a PFX/P12 file."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12

    private_key, certificate, _ = pkcs12.load_key_and_certificates(
        pfx_bytes, password.encode("utf-8")
    )

    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    cert_pem = certificate.public_bytes(
        serialization.Encoding.PEM
    ).decode("utf-8")

    return key_pem, cert_pem
