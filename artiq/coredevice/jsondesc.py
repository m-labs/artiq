from os import path
import json
from jsonschema import Draft7Validator, validators

def extend_with_default(validator_class):
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for property, subschema in properties.items():
            if "default" in subschema:
                instance.setdefault(property, subschema["default"])

            for error in validate_properties(
                validator, properties, instance, schema,
            ):
                yield error

    return validators.extend(
        validator_class, {"properties" : set_defaults},
    )

schema_path = path.join(path.dirname(__file__), "coredevice_generic.schema.json")
with open(schema_path, "r") as f:
    schema = json.load(f)

validator = extend_with_default(Draft7Validator)(schema)

def load(description_path):
    with open(description_path, "r") as f:
        result = json.load(f)

    global validator
    validator.validate(result)

    return result
