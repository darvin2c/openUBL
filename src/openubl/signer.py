"""
XML Digital Signing for SUNAT electronic documents.
Uses signxml for pure-Python XML signing.

Normative basis:
- RS N.° 300-2014/SUNAT and modifications: XMLDSig signature placed inside
  ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent.
- Resolución de Secretaría N.° 007-2024-PCM/SGTD: approves Directiva
  N.° 002-2024-PCM/SGTD on the use of digital signatures by public entities.
- INDECOPI/IOFE "Guía de Acreditación de Entidades de Certificación":
  requires SHA-2 family signature algorithms (RSA-SHA-256/384/512 or ECDSA).

Algorithm URIs used:
- SignatureMethod: http://www.w3.org/2001/04/xmldsig-more#rsa-sha256
- DigestMethod: http://www.w3.org/2001/04/xmlenc#sha256
- CanonicalizationMethod: http://www.w3.org/TR/2001/REC-xml-c14n-20010315
"""
from lxml import etree
from signxml import XMLSigner


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
        digest_algorithm="sha256",
        signature_algorithm="rsa-sha256",
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
