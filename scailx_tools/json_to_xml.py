import json
from json2xml import json2xml

def convert_json_file_to_xml_file(json_filename, xml_filename, root_element_name="root"):
    with open(json_filename, 'r') as f:
        data = json.load(f)

    # Convert the dictionary to XML
    xml_data = json2xml.Json2xml(
        data,
        wrapper=root_element_name,
        pretty=True,
        attr_type=False
    ).to_xml()

    # Write the XML output to a file
    with open(xml_filename, 'w') as f:
        f.write(xml_data)

convert_json_file_to_xml_file("IMX678_Basic_1920x1080.json", "IMX678_Basic_1920x1080.xml")


