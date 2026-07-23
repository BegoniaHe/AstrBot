from astrbot.core.agent.tool import FunctionTool, ToolSet


def test_google_schema_fills_missing_array_items_with_string_schema():
    tool = FunctionTool(
        name="search_sources",
        description="Search sources by UUID.",
        parameters={
            "type": "object",
            "properties": {
                "source_uuids": {
                    "type": "array",
                    "description": "Optional list of source UUIDs.",
                }
            },
            "required": ["source_uuids"],
        },
    )

    schema = ToolSet([tool]).google_schema()
    source_uuids = schema["function_declarations"][0]["parameters"]["properties"][
        "source_uuids"
    ]

    assert source_uuids["type"] == "array"
    assert source_uuids["items"] == {"type": "string"}
