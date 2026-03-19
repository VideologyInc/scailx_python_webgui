import xmltodict
import json


def xml_to_json(xml_name, json_name):
    # Open the XML file and read its content
    with open(xml_name, "r") as xml_file:
        xml_content = xml_file.read()

    # Convert the XML content to a Python dictionary
    data_dict = xmltodict.parse(xml_content)

    # Open a new JSON file in write mode and dump the dictionary as JSON
    with open(json_name, "w") as json_file:
        # Use json.dump() to write directly to the file, indent for readability
        json.dump(data_dict, json_file, indent=4)



xml_to_json("IMX900_Basic_1920x1080.xml", "IMX900_Basic_1920x1080.json")
