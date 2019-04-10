import yamale


schema = yamale.make_schema('./schema.yaml')

# Create a Data object
data = yamale.make_data('./data.yaml')

# Validate data against the schema. Throws a ValueError if data is invalid.
result = yamale.validate(schema, data)

if not result:
    raise Exception("Empty input")

print("Valid yaml!")
