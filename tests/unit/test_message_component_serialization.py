import inspect

import pytest

from astrbot.core.message.components import (
    Anonymous,
    At,
    BaseMessageComponent,
    FlashTransfer,
    Forward,
    Node,
    Nodes,
    OnlineFile,
    Plain,
    Poke,
    Reply,
)


@pytest.mark.asyncio
async def test_message_components_use_only_async_serialization_api():
    assert inspect.iscoroutinefunction(BaseMessageComponent.to_dict)
    assert not hasattr(BaseMessageComponent, "toDict")

    components = [
        Plain(text="mock text"),
        Anonymous(ignore=1),
        At(qq="10001"),
        OnlineFile(
            msg_id="mock-message",
            element_id="mock-element",
            file_name="mock.txt",
            file_size="128",
            is_dir=False,
        ),
        Reply(id="mock-reply"),
        Poke(id="10002"),
        Forward(id="mock-forward"),
        FlashTransfer(file_set_id="mock-file-set"),
    ]

    payloads = [await component.to_dict() for component in components]

    assert [payload["type"] for payload in payloads] == [
        "text",
        "anonymous",
        "at",
        "onlinefile",
        "reply",
        "poke",
        "forward",
        "flashtransfer",
    ]
    assert all(not hasattr(component, "toDict") for component in components)


@pytest.mark.asyncio
async def test_nested_nodes_use_async_component_serialization():
    node = Node(
        uin="10001",
        name="Mock Sender",
        content=[Forward(id="mock-forward"), Plain(text="mock content")],
    )

    payload = await Nodes(nodes=[node]).to_dict()

    assert payload == {
        "messages": [
            {
                "type": "node",
                "data": {
                    "user_id": "10001",
                    "nickname": "Mock Sender",
                    "content": [
                        {"type": "forward", "data": {"id": "mock-forward"}},
                        {"type": "text", "data": {"text": "mock content"}},
                    ],
                },
            }
        ]
    }
