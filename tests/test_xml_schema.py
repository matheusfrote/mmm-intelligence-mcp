"""Bounded local XML schemas validate types without loading external resources."""

import base64

import pytest
from test_file_formats import payload

XSD = b"""<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
<xs:element name="root"><xs:complexType><xs:sequence>
<xs:element name="record" maxOccurs="unbounded"><xs:complexType><xs:sequence>
<xs:element name="count" type="xs:integer"/>
</xs:sequence></xs:complexType></xs:element>
</xs:sequence></xs:complexType></xs:element></xs:schema>"""


def request(xml, schema=XSD):
    return payload(
        "xml",
        xml,
        xml_record="record",
        xml_fields={"count": "count"},
        xml_schema_base64=base64.b64encode(schema).decode(),
    )


def test_schema_accepts_integer_and_rejects_non_integer(service):
    good = service.call(
        "preview_dataset", request(b"<root><record><count>12</count></record></root>")
    )
    assert good.ok, good.error
    bad = service.call(
        "preview_dataset", request(b"<root><record><count>twelve</count></record></root>")
    )
    assert not bad.ok and bad.error.code == "XML_SCHEMA"


@pytest.mark.parametrize(
    "schema",
    [
        b'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"><xs:include schemaLocation="file:///C:/secret"/></xs:schema>',
        b'<!DOCTYPE schema [<!ENTITY x SYSTEM "http://invalid.local/">]><schema>&x;</schema>',
        b'<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"><xs:pattern value="(a+)+"/></xs:schema>',
        b"<broken>",
    ],
)
def test_unsafe_external_complex_or_malformed_schemas_fail_closed(service, schema):
    bad = service.call(
        "preview_dataset", request(b"<root><record><count>1</count></record></root>", schema)
    )
    assert not bad.ok and bad.error.code == "XML_SCHEMA"
